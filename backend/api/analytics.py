from collections import Counter

from fastapi import APIRouter

from backend import db
from backend.paypal import client

router = APIRouter(tags=["analytics"])
PAID = {"PAID", "MARKED_AS_PAID"}


@router.get("/analytics")
def analytics():
    calls = db.list_calls()
    invoices = {}
    for raw in client.list_invoices():
        inv = client.normalize(raw)
        invoices[inv["id"]] = inv

    paid_times = db.paid_times()
    paid_ids = {i for i, inv in invoices.items() if inv["status"] in PAID} | set(paid_times)

    first_call = {}
    for c in calls:
        iid = c["invoice_id"]
        t = c["created_at"] or c["updated_at"] or 0
        if iid and (iid not in first_call or t < first_call[iid]):
            first_call[iid] = t

    contacted = set(first_call)
    paid_contacted = contacted & paid_ids

    durations = [
        max(paid_times[i] - first_call[i], 0)
        for i in paid_contacted
        if i in paid_times
    ]
    recovered = sum(
        float((invoices.get(i) or {}).get("total") or (invoices.get(i) or {}).get("amount") or 0)
        for i in paid_contacted
    )

    promises = Counter()
    for c in calls:
        if not c["promise_date"]:
            continue
        result = c["promise_result"]
        if not result:
            result = "kept" if c["invoice_id"] in paid_ids else "pending"
        promises[result] += 1

    outcomes = Counter()
    for c in calls:
        if c["status"] not in ("done", "unreachable"):
            continue
        o = c["outcome"]
        if c["status"] == "unreachable":
            o = "no_answer"
        if o == "dispute_resolved":
            o = "disputed"
        if o:
            outcomes[o] += 1

    return {
        "contacted": len(contacted),
        "paid": len(paid_contacted),
        "recovery_rate": round(100 * len(paid_contacted) / len(contacted)) if contacted else None,
        "recovered_amount": recovered,
        "avg_seconds_to_pay": sum(durations) / len(durations) if durations else None,
        "promises": {
            "kept": promises["kept"],
            "broken": promises["broken"],
            "pending": promises["pending"],
        },
        "outcomes": dict(outcomes),
    }