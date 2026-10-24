from typing import Annotated, TypedDict

from langgraph.graph.message import add_messages


class Invoice(TypedDict):
    id: str
    number: str
    status: str
    client_name: str
    client_email: str
    amount: str
    currency: str
    due_date: str
    days_overdue: int


class CollectionState(TypedDict, total=False):
    overdue: list[Invoice]
    current: Invoice | None
    tone: str
    messages: Annotated[list, add_messages]
    pending_request: dict | None
    needs_approval: bool
    awaiting_reply: bool
    followup_sent: bool
    approved: bool | None
    target_invoice_id: str | None
    outcome: str
    promise_date: str | None