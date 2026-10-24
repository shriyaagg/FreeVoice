from backend import config
from backend.agent.state import CollectionState
from backend.paypal import client


def scan_node(state: CollectionState) -> dict:
    invoices = [client.normalize(i) for i in client.list_invoices()]
    collectable = config.POLICY["collectable_statuses"]
    overdue = [
        i for i in invoices
        if i["status"] in collectable and i["days_overdue"] > 0
    ]
    overdue.sort(key=lambda i: i["days_overdue"], reverse=True)
    return {"overdue": overdue}