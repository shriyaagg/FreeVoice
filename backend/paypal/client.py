import time
from datetime import date, timedelta

import httpx

from backend import config

_token = {"value": None, "expires": 0.0}

def create_and_send_invoice(first, last, email, item, amount, due_date) -> str:
    due = date.fromisoformat(due_date)
    body = {
        "detail": {
            "invoice_date": (due - timedelta(days=14)).isoformat(),
            "currency_code": "USD",
            "payment_term": {"term_type": "DUE_ON_DATE_SPECIFIED", "due_date": due_date},
        },
        "primary_recipients": [
            {"billing_info": {
                "name": {"given_name": first, "surname": last},
                "email_address": email,
            }}
        ],
        "items": [{
            "name": item,
            "quantity": "1",
            "unit_amount": {"currency_code": "USD", "value": f"{float(amount):.2f}"},
        }],
    }
    created = _request("POST", "/v2/invoicing/invoices", json=body)
    invoice_id = created["href"].rstrip("/").split("/")[-1]
    _request(
        "POST",
        f"/v2/invoicing/invoices/{invoice_id}/send",
        json={"send_to_recipient": True, "send_to_invoicer": False},
    )
    return invoice_id


def _get_token() -> str:
    if _token["value"] and time.time() < _token["expires"] - 60:
        return _token["value"]
    r = httpx.post(
        f"{config.PAYPAL_BASE_URL}/v1/oauth2/token",
        auth=(config.PAYPAL_CLIENT_ID, config.PAYPAL_SECRET),
        data={"grant_type": "client_credentials"},
        timeout=20,
    )
    r.raise_for_status()
    data = r.json()
    _token["value"] = data["access_token"]
    _token["expires"] = time.time() + data["expires_in"]
    return _token["value"]


def _request(method: str, path: str, **kwargs) -> dict:
    r = httpx.request(
        method,
        f"{config.PAYPAL_BASE_URL}{path}",
        headers={"Authorization": f"Bearer {_get_token()}"},
        timeout=30,
        **kwargs,
    )
    r.raise_for_status()
    return r.json() if r.content else {}


def list_invoices(page_size: int = 50) -> list[dict]:
    data = _request(
        "GET",
        "/v2/invoicing/invoices",
        params={"page": 1, "page_size": page_size, "total_required": "true"},
    )
    return data.get("items", [])


def normalize(raw: dict) -> dict:
    detail = raw.get("detail", {})
    billing = (raw.get("primary_recipients") or [{}])[0].get("billing_info", {})
    name = billing.get("name", {})
    amount = raw.get("due_amount") or raw.get("amount") or {}
    due = detail.get("payment_term", {}).get("due_date")
    total = (raw.get("amount") or {}).get("value") or amount.get("value")
    days = (date.today() - date.fromisoformat(due)).days if due else 0
    return {
        "id": raw.get("id"),
        "number": detail.get("invoice_number"),
        "status": raw.get("status"),
        "client_name": f"{name.get('given_name', '')} {name.get('surname', '')}".strip()
        or billing.get("business_name", ""),
        "client_email": billing.get("email_address"),
        "amount": amount.get("value"),
        "total": total,
        "currency": amount.get("currency_code"),
        "due_date": due,
        "days_overdue": max(days, 0),
    }