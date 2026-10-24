import os
from datetime import date, timedelta

import httpx

from backend.paypal.client import _request

CLIENTS = [
    ("Aarav", "Mehta", os.getenv("DEMO_CLIENT_EMAIL", "aarav@example.com"), "Logo design", "450.00", 12),
    ("Priya", "Nair", "priya@example.com", "Website build", "1200.00", 25),
    ("Rohan", "Kapoor", "rohan@example.com", "Monthly retainer", "800.00", 40),
    ("Sara", "Khan", "sara@example.com", "Copywriting", "300.00", 5),
    ("Dev", "Malhotra", "dev@example.com", "App prototype", "2500.00", 60),
    ("Neha", "Gupta", "neha@example.com", "Photo shoot", "650.00", 18),
]


def make_invoice(first, last, email, item, amount, days_overdue):
    today = date.today()
    due = today - timedelta(days=days_overdue)
    invoice_date = due - timedelta(days=14)
    body = {
        "detail": {
            "invoice_date": invoice_date.isoformat(),
            "currency_code": "USD",
            "payment_term": {
                "term_type": "DUE_ON_DATE_SPECIFIED",
                "due_date": due.isoformat(),
            },
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
            "unit_amount": {"currency_code": "USD", "value": amount},
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


if __name__ == "__main__":
    for c in CLIENTS:
        try:
            inv_id = make_invoice(*c)
            print(f"created {inv_id} for {c[0]} {c[1]} ({c[5]} days overdue)")
        except httpx.HTTPStatusError as e:
            print(f"failed for {c[0]}: {e.response.text}")