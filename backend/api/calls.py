import time
import uuid

from fastapi import APIRouter, HTTPException
from langgraph.types import Command
from pydantic import BaseModel

from backend import config, db
from backend.agent.graph import get_graph
from backend.agent.nodes.call import as_text
from backend.paypal import client

router = APIRouter(prefix="/calls", tags=["calls"])
graph = get_graph()
ACTIVE = {"ringing", "missed", "awaiting_client", "awaiting_owner"}


class StartBody(BaseModel):
    invoice_id: str


class MessageBody(BaseModel):
    text: str


class ApprovalBody(BaseModel):
    approved: bool


def _agent_says(new_messages) -> str:
    parts = []
    for m in new_messages:
        if m.type == "ai":
            text = as_text(m.content).strip()
            if text:
                parts.append(text)
    return " ".join(parts)


def _transcript(messages) -> list[dict]:
    out = []
    for m in messages:
        text = as_text(m.content).strip()
        if m.type == "human" and text and not text.startswith("(The client"):
            out.append({"role": "client", "text": text})
        elif m.type == "ai" and text:
            out.append({"role": "agent", "text": text})
    return out


def _describe(request) -> str:
    if not request:
        return "Request"
    value = request.get("value")
    num = str(int(value)) if isinstance(value, (int, float)) else ""
    if request.get("type") == "extension_days":
        return f"{num}-day extension" if num else "Extension"
    if request.get("type") == "discount_percent":
        return f"{num}% discount" if num else "Discount"
    return "Request"


def _summarize(escalation, decision, values) -> str:
    parts = []
    if escalation:
        text = f"asked for a {escalation.lower()}"
        if decision:
            text += f", freelancer {decision}"
        parts.append(text)
    outcome = values.get("outcome")
    if outcome == "promised" and values.get("promise_date"):
        parts.append(f"agreed to pay by {values['promise_date']}")
    elif outcome == "paid_now":
        parts.append("agreed to pay right away")
    elif outcome == "refused":
        parts.append("refused to pay")
    elif outcome == "disputed":
        reason = values.get("dispute_reason") or "no reason given"
        parts.append(f"disputed the invoice ({reason})")
    if not parts:
        return "Call ended without a clear outcome."
    s = ", ".join(parts)
    return s[0].upper() + s[1:] + "."


def _history(call: dict) -> tuple[str, bool]:
    lines, broken = [], False
    for c in db.calls_for_invoice(call["invoice_id"]):
        if c["call_id"] == call["call_id"] or c["status"] != "done":
            continue
        when = time.strftime("%b %d", time.localtime(c["created_at"] or 0))
        lines.append(f"- {when}: {c.get('summary') or c.get('outcome')}")
        if c.get("promise_result") == "broken":
            broken = True
    return "\n".join(lines), broken


def _step(call_id: str, payload) -> dict:
    cfg = {"configurable": {"thread_id": call_id}}
    before = db.get_call(call_id) or {}
    try:
        n_prev = len(graph.get_state(cfg).values.get("messages", []))
        result = graph.invoke(payload, cfg)
    except Exception as e:
        raise HTTPException(502, f"Agent error: {e}")

    values = graph.get_state(cfg).values
    invoice = values.get("current")
    if not invoice:
        raise HTTPException(404, "No matching overdue invoice found")

    approval = None
    interrupts = result.get("__interrupt__")
    if interrupts:
        p = interrupts[0].value
        if p.get("type") == "approval":
            status = "awaiting_owner"
            approval = {"request": p["request"], "message": p["message"]}
        else:
            status = "awaiting_client"
    else:
        status = "done"

    messages = values.get("messages", [])
    approved = values.get("approved")
    decision = "approved" if approved is True else "denied" if approved is False else None
    response = {
        "call_id": call_id,
        "status": status,
        "agent_says": _agent_says(messages[n_prev:]),
        "approval": approval,
        "outcome": values.get("outcome"),
        "promise_date": values.get("promise_date"),
        "owner_decision": decision,
    }

    fields = dict(
        invoice_id=invoice["id"],
        invoice_number=invoice["number"],
        client_name=invoice["client_name"],
        amount=invoice["amount"],
        currency=invoice["currency"],
        status=status,
        outcome=values.get("outcome"),
        promise_date=values.get("promise_date"),
        approval=approval,
        owner_decision=decision,
        transcript=_transcript(messages),
    )
    if approval:
        fields["escalation"] = _describe(approval["request"])
    if status == "done":
        escalation = fields.get("escalation") or before.get("escalation")
        fields["summary"] = _summarize(escalation, decision, values)
        if values.get("dispute_reason"):
            fields["dispute_reason"] = values["dispute_reason"]
    db.save_call(call_id, **fields)
    return response


def _require(call_id: str, status: str) -> dict:
    call = db.get_call(call_id)
    if not call:
        raise HTTPException(404, "Call not found")
    if call["status"] != status:
        raise HTTPException(409, f"Call is {call['status']}, expected {status}")
    return call


@router.post("")
def start_call(body: StartBody):
    latest = db.latest_calls_by_invoice().get(body.invoice_id)
    if latest and latest["status"] in ACTIVE:
        raise HTTPException(409, "A call for this invoice is already in progress")
    if latest and latest["outcome"] == "disputed":
        raise HTTPException(409, "This invoice is under dispute. Resolve it first.")
    try:
        inv = client.get_invoice(body.invoice_id)
    except Exception:
        raise HTTPException(404, "Invoice not found")
    if inv["status"] not in config.POLICY["collectable_statuses"] or inv["days_overdue"] <= 0:
        raise HTTPException(400, "Invoice is not overdue or is already settled")

    call_id = uuid.uuid4().hex[:12]
    db.save_call(
        call_id,
        invoice_id=inv["id"],
        invoice_number=inv["number"],
        client_name=inv["client_name"],
        amount=inv["amount"],
        currency=inv["currency"],
        status="ringing",
        kind="first",
        attempts=1,
        ring_started_at=time.time(),
        transcript=[],
    )
    return {"call_id": call_id, "status": "ringing", "attempts": 1}


@router.post("/{call_id}/answer")
def answer(call_id: str):
    call = db.get_call(call_id)
    if not call:
        raise HTTPException(404, "Call not found")
    if call["status"] not in ("ringing", "missed"):
        raise HTTPException(409, f"Call is {call['status']}")
    history, broken = _history(call)
    return _step(
        call_id,
        {
            "target_invoice_id": call["invoice_id"],
            "history": history,
            "broken_promise": broken,
        },
    )


@router.post("/{call_id}/messages")
def send_message(call_id: str, body: MessageBody):
    _require(call_id, "awaiting_client")
    return _step(call_id, Command(resume=body.text))


@router.post("/{call_id}/approval")
def decide(call_id: str, body: ApprovalBody):
    _require(call_id, "awaiting_owner")
    return _step(call_id, Command(resume=body.approved))


@router.post("/{call_id}/resolve-dispute")
def resolve_dispute(call_id: str):
    call = db.get_call(call_id)
    if not call:
        raise HTTPException(404, "Call not found")
    if call["outcome"] != "disputed":
        raise HTTPException(409, "Call is not disputed")
    summary = (call.get("summary") or "").rstrip(".")
    db.save_call(
        call_id,
        outcome="dispute_resolved",
        summary=f"{summary}. Dispute resolved by the freelancer.",
    )
    return {"ok": True}


@router.get("")
def list_all(status: str | None = None, outcome: str | None = None):
    return db.list_calls(status, outcome)


@router.get("/{call_id}/public")
def public_view(call_id: str):
    call = db.get_call(call_id)
    if not call:
        raise HTTPException(404, "Call not found")
    return {
        "call_id": call["call_id"],
        "status": call["status"],
        "attempts": call.get("attempts"),
        "invoice_number": call["invoice_number"],
        "amount": call["amount"],
        "currency": call["currency"],
        "transcript": call["transcript"] or [],
        "outcome": call["outcome"],
        "promise_date": call["promise_date"],
    }


@router.get("/{call_id}")
def get_one(call_id: str):
    call = db.get_call(call_id)
    if not call:
        raise HTTPException(404, "Call not found")
    return call