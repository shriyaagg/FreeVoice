import asyncio
import time
import uuid
from datetime import date

from backend import config, db
from backend.paypal import client

PAID = ("PAID", "MARKED_AS_PAID")


def _is_paid(invoice_id: str) -> bool:
    if invoice_id in db.paid_invoice_ids():
        return True
    try:
        paid = client.get_invoice(invoice_id)["status"] in PAID
    except Exception:
        return False
    if paid:
        db.mark_paid(invoice_id)
    return paid


def _give_up(call: dict):
    try:
        client.send_reminder(
            call["invoice_id"],
            "We tried to reach you by phone about this invoice. "
            "Please use the link to pay, or contact the freelancer to arrange a date.",
        )
    except Exception as e:
        print("reminder failed:", e)
    attempts = call["attempts"] or 1
    db.save_call(
        call["call_id"],
        status="unreachable",
        outcome="no_answer",
        summary=f"No answer after {attempts} attempts. Payment reminder sent by email.",
    )


def _check_rings(now: float):
    policy = config.POLICY
    max_attempts = policy["max_calls_per_invoice"]
    delays = policy.get("retry_delay_minutes", [1])

    for call in db.list_calls("ringing"):
        if now - (call["ring_started_at"] or now) < policy["ring_timeout_seconds"]:
            continue
        attempts = call["attempts"] or 1
        if attempts >= max_attempts:
            _give_up(call)
        else:
            wait = delays[min(attempts - 1, len(delays) - 1)] * 60
            db.save_call(call["call_id"], status="missed", next_ring_at=now + wait)

    for call in db.list_calls("missed"):
        if not call["next_ring_at"] or now < call["next_ring_at"]:
            continue
        if _is_paid(call["invoice_id"]):
            db.save_call(
                call["call_id"], status="done", outcome="paid",
                summary="Paid before the next call attempt.",
            )
            continue
        db.save_call(
            call["call_id"],
            status="ringing",
            attempts=(call["attempts"] or 1) + 1,
            ring_started_at=now,
            next_ring_at=None,
        )


def _check_promises():
    today = date.today().isoformat()
    limit = config.POLICY.get("max_followups", 2)
    for invoice_id, call in db.latest_calls_by_invoice().items():
        if call["status"] != "done" or call["outcome"] != "promised":
            continue
        if call["promise_result"] or not call["promise_date"]:
            continue
        if call["promise_date"] >= today:
            continue
        if _is_paid(invoice_id):
            db.save_call(call["call_id"], promise_result="kept")
            continue
        db.save_call(call["call_id"], promise_result="broken")
        if db.count_calls(invoice_id, "promised") <= limit:
            db.save_call(
                uuid.uuid4().hex[:12],
                invoice_id=invoice_id,
                invoice_number=call["invoice_number"],
                client_name=call["client_name"],
                amount=call["amount"],
                currency=call["currency"],
                status="ringing",
                kind="follow_up",
                attempts=1,
                ring_started_at=time.time(),
                transcript=[],
            )


def tick():
    _check_rings(time.time())
    _check_promises()


async def run_scheduler():
    while True:
        try:
            await asyncio.to_thread(tick)
        except Exception as e:
            print("scheduler error:", e)
        await asyncio.sleep(5)