from langchain_core.tools import tool
from paypal_agent_toolkit.langchain.toolkit import PayPalToolkit
from paypal_agent_toolkit.shared.configuration import Configuration, Context
from datetime import date

from backend import config


def paypal_tools():
    toolkit = PayPalToolkit(
        client_id=config.PAYPAL_CLIENT_ID,
        secret=config.PAYPAL_SECRET,
        configuration=Configuration(
            actions={
                "invoices": {
                    "create": True,
                    "list": True,
                    "send": True,
                    "sendReminder": True,
                    "generateQRC": True,
                }
            },
            context=Context(sandbox=True),
        ),
    )
    return toolkit.get_tools()


@tool
def check_policy(request_type: str, value: float) -> dict:
    """Check a client's request against the owner's policy.
    request_type is 'extension_days' or 'discount_percent'."""
    limits = {
        "extension_days": config.POLICY["max_extension_days"],
        "discount_percent": config.POLICY["max_discount_percent"],
    }
    if request_type not in limits:
        return {"allowed": False, "limit": None, "reason": "unknown request type"}
    limit = limits[request_type]
    return {"allowed": value <= limit, "limit": limit}


@tool
def record_promise(invoice_id: str, promise_date: str) -> str:
    """Record the date (YYYY-MM-DD) the client promised to pay."""
    try:
        d = date.fromisoformat(promise_date)
    except ValueError:
        return "Error: date must be in YYYY-MM-DD format. Ask the client to confirm the date."
    if d < date.today():
        return "Error: that date is in the past. Work out the correct upcoming date and try again."
    return f"Recorded promise for {invoice_id} on {promise_date}"


def all_tools():
    return [*paypal_tools(), check_policy, record_promise]

@tool
def end_call(outcome: str, request_type: str = "", request_value: float = 0) -> str:
    """End the call. outcome is one of: paid_now, promised, needs_approval, refused, no_answer.
    If outcome is needs_approval, also set request_type ('extension_days' or
    'discount_percent') and request_value (the number the client asked for)."""
    return f"Call ended with outcome {outcome}"

SAFE_PAYPAL_KEYWORDS = ("reminder", "qr")


def call_tools():
    paypal = [
        t for t in paypal_tools()
        if any(k in t.name.lower() for k in SAFE_PAYPAL_KEYWORDS)
    ]
    return [*paypal, check_policy, record_promise, end_call]