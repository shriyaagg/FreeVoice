import uuid

from fastapi import APIRouter, HTTPException
from langgraph.types import Command
from pydantic import BaseModel

from backend import db
from backend.agent.graph import get_graph
from backend.agent.nodes.call import as_text

router = APIRouter(prefix="/calls", tags=["calls"])
graph = get_graph()


class StartBody(BaseModel):
    invoice_id: str | None = None


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

def _step(call_id: str, payload) -> dict:
    cfg = {"configurable": {"thread_id": call_id}}
    try:
        prev = len(graph.get_state(cfg).values.get("messages", []))
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
        "agent_says": _agent_says(messages[prev:]),
        "approval": approval,
        "outcome": values.get("outcome"),
        "promise_date": values.get("promise_date"),
        "owner_decision": decision,
    }
    extra = {"escalation": _describe(approval["request"])} if approval else {}
    db.save_call(
        call_id,
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
        **extra,
    )
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
    call_id = uuid.uuid4().hex[:12]
    payload = {"target_invoice_id": body.invoice_id} if body.invoice_id else {}
    return _step(call_id, payload)


@router.post("/{call_id}/messages")
def send_message(call_id: str, body: MessageBody):
    _require(call_id, "awaiting_client")
    return _step(call_id, Command(resume=body.text))


@router.post("/{call_id}/approval")
def decide(call_id: str, body: ApprovalBody):
    _require(call_id, "awaiting_owner")
    return _step(call_id, Command(resume=body.approved))


@router.get("")
def list_all(status: str | None = None):
    return db.list_calls(status)


@router.get("/{call_id}")
@router.get("/{call_id}/public")
def public_view(call_id: str):
    call = db.get_call(call_id)
    if not call:
        raise HTTPException(404, "Call not found")
    return {
        "call_id": call["call_id"],
        "status": call["status"],
        "invoice_number": call["invoice_number"],
        "amount": call["amount"],
        "currency": call["currency"],
        "transcript": call["transcript"] or [],
        "outcome": call["outcome"],
        "promise_date": call["promise_date"],
    }
def get_one(call_id: str):
    call = db.get_call(call_id)
    if not call:
        raise HTTPException(404, "Call not found")
    return call