import calendar
import re
from datetime import date, timedelta

from langchain_core.messages import AIMessage, HumanMessage

from backend import config

WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5}
_counter = 0


def _call(name: str, **args) -> dict:
    global _counter
    _counter += 1
    return {"name": name, "args": args, "id": f"mock-{_counter}", "type": "tool_call"}


def _parse_days(low: str) -> int | None:
    m = re.search(r"(\d+|one|two|three|four|five)\s*(?:more\s*)?(day|week)s?", low)
    if not m:
        return None
    n = int(m.group(1)) if m.group(1).isdigit() else WORDS[m.group(1)]
    return n * (7 if m.group(2) == "week" else 1)


def _day_of_month(day: int) -> date:
    today = date.today()
    year, month = today.year, today.month
    if day < today.day:
        month += 1
        if month == 13:
            year, month = year + 1, 1
    return date(year, month, min(day, calendar.monthrange(year, month)[1]))


def _promise(inv: dict, d: date) -> AIMessage:
    return AIMessage(
        content=f"Thank you, I've noted {d.strftime('%B %d')}. Goodbye.",
        tool_calls=[
            _call("record_promise", invoice_id=inv["id"], promise_date=d.isoformat()),
            _call("end_call", outcome="promised"),
        ],
    )


def mock_reply(state: dict, messages: list) -> AIMessage:
    inv = state["current"]
    name = (inv["client_name"] or "there").split()[0]
    limit = config.POLICY["max_extension_days"]
    humans = [m for m in messages if isinstance(m, HumanMessage)]
    said = humans[-1].content if humans else ""
    low = said.lower() if isinstance(said, str) else ""

    if not any(m.type == "ai" for m in messages):
        return AIMessage(content=(
            f"Hello {name}, I am an AI assistant calling on behalf of the freelancer "
            f"regarding invoice {inv['number']} for {inv['amount']} {inv['currency']}, "
            f"which is {inv['days_overdue']} days overdue. "
            "Can you pay today, or give me a firm date?"
        ))

    if state.get("followup_sent"):
        if re.search(r"\b(no|can't|cannot|won't|not)\b", low):
            return AIMessage(
                content="Understood, I'll pass that on to the freelancer. Goodbye.",
                tool_calls=[_call("end_call", outcome="refused")],
            )
        default = int((state.get("pending_request") or {}).get("value") or limit) \
            if state.get("approved") else limit
        return _promise(inv, date.today() + timedelta(days=_parse_days(low) or default))

    if re.search(r"(won't pay|refuse|not paying|can't pay)", low):
        return AIMessage(
            content="Understood, I'll let the freelancer know. Goodbye.",
            tool_calls=[_call("end_call", outcome="refused")],
        )

    days = _parse_days(low)
    if days is not None:
        if days > limit:
            return AIMessage(
                content="I can't approve that myself. I'll check with the freelancer and get back to you. Thanks for your time.",
                tool_calls=[_call("end_call", outcome="needs_approval",
                                  request_type="extension_days", request_value=float(days))],
            )
        return _promise(inv, date.today() + timedelta(days=days))

    m = re.search(r"\b(\d{1,2})(?:st|nd|rd|th)\b", low)
    if m:
        return _promise(inv, _day_of_month(int(m.group(1))))

    if re.search(r"\b(now|today|right away|paying)\b", low):
        return AIMessage(
            content="Great, thank you. I'll send the payment link now. Goodbye.",
            tool_calls=[_call("end_call", outcome="paid_now")],
        )

    return AIMessage(content="Could you give me a specific date, or a number of days?")