from datetime import date, timedelta

from fastapi import APIRouter, HTTPException

from backend import config, db

router = APIRouter(prefix="/demo", tags=["demo"])


@router.post("/expire-promise/{invoice_id}")
def expire_promise(invoice_id: str):
    if not config.DEMO_MODE:
        raise HTTPException(404, "Not found")
    call = db.latest_calls_by_invoice().get(invoice_id)
    if not call or call["outcome"] != "promised":
        raise HTTPException(400, "No active promise on this invoice")
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    db.save_call(call["call_id"], promise_date=yesterday)
    return {"promise_date": yesterday}