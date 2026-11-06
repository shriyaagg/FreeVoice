import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend import db
from backend.paypal import client

router = APIRouter(tags=["dashboard"])
PAID_STATUSES = {"PAID", "MARKED_AS_PAID"}
HIDDEN_STATUSES = {"DRAFT", "CANCELLED"}


@router.get("/dashboard")
def dashboard():
    invoices = [client.normalize(i) for i in client.list_invoices()]
    latest = db.latest_calls_by_invoice()
    webhook_paid = db.paid_invoice_ids()
    rows = []
    for inv in invoices:
        if inv["status"] in HIDDEN_STATUSES:
            continue
        call = latest.get(inv["id"]) or {}
        paid = inv["status"] in PAID_STATUSES or inv["id"] in webhook_paid
        if paid and inv["id"] not in webhook_paid:
            db.mark_paid(inv["id"])
        rows.append({
            **inv,
            "days_overdue": 0 if paid else inv["days_overdue"],
            "paid": paid,
            "last_call_id": call.get("call_id"),
            "call_status": call.get("status"),
            "kind": call.get("kind"),
            "attempts": call.get("attempts"),
            "outcome": call.get("outcome"),
            "promise_date": call.get("promise_date"),
            "summary": call.get("summary"),
            "dispute_reason": call.get("dispute_reason"),
        })
    return rows


class NewInvoice(BaseModel):
    first_name: str
    last_name: str
    email: str
    description: str
    amount: float
    due_date: str


@router.post("/invoices")
def create_invoice(body: NewInvoice):
    try:
        invoice_id = client.create_and_send_invoice(
            body.first_name, body.last_name, body.email,
            body.description, body.amount, body.due_date,
        )
    except httpx.HTTPStatusError as e:
        raise HTTPException(400, e.response.text)
    return {"id": invoice_id}