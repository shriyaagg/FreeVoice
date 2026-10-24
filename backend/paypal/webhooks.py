import httpx
from fastapi import APIRouter, HTTPException, Request

from backend import config, db
from backend.paypal.client import _get_token

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


def _verified(headers, event: dict) -> bool:
    if not config.PAYPAL_WEBHOOK_ID:
        return True  # local dev only, no webhook registered yet
    body = {
        "auth_algo": headers.get("paypal-auth-algo"),
        "cert_url": headers.get("paypal-cert-url"),
        "transmission_id": headers.get("paypal-transmission-id"),
        "transmission_sig": headers.get("paypal-transmission-sig"),
        "transmission_time": headers.get("paypal-transmission-time"),
        "webhook_id": config.PAYPAL_WEBHOOK_ID,
        "webhook_event": event,
    }
    r = httpx.post(
        f"{config.PAYPAL_BASE_URL}/v1/notifications/verify-webhook-signature",
        headers={"Authorization": f"Bearer {_get_token()}"},
        json=body,
        timeout=20,
    )
    return r.status_code == 200 and r.json().get("verification_status") == "SUCCESS"


@router.post("/paypal")
async def paypal_webhook(request: Request):
    event = await request.json()
    if not _verified(request.headers, event):
        raise HTTPException(400, "Invalid webhook signature")
    if event.get("event_type") == "INVOICING.INVOICE.PAID":
        resource = event.get("resource", {})
        invoice_id = (resource.get("invoice") or {}).get("id") or resource.get("id")
        if invoice_id:
            db.mark_paid(invoice_id)
    return {"ok": True}