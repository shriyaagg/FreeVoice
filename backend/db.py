import json
import sqlite3
import time
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "calls.db"
JSON_FIELDS = ("approval", "transcript")


def _conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with _conn() as c:
        c.execute(
            """CREATE TABLE IF NOT EXISTS calls (
                call_id TEXT PRIMARY KEY,
                invoice_id TEXT, invoice_number TEXT, client_name TEXT,
                amount TEXT, currency TEXT,
                status TEXT, outcome TEXT, promise_date TEXT,
                approval TEXT, owner_decision TEXT, escalation TEXT, transcript TEXT,
                updated_at REAL
            )"""
        )
        c.execute(
            "CREATE TABLE IF NOT EXISTS payments (invoice_id TEXT PRIMARY KEY, paid_at REAL)"
        )


def save_call(call_id: str, **fields):
    fields["updated_at"] = time.time()
    for k in JSON_FIELDS:
        if fields.get(k) is not None:
            fields[k] = json.dumps(fields[k])
    cols = ["call_id", *fields]
    vals = [call_id, *fields.values()]
    updates = ", ".join(f"{k}=excluded.{k}" for k in fields)
    sql = (
        f"INSERT INTO calls ({', '.join(cols)}) "
        f"VALUES ({', '.join('?' for _ in cols)}) "
        f"ON CONFLICT(call_id) DO UPDATE SET {updates}"
    )
    with _conn() as c:
        c.execute(sql, vals)


def _row(r) -> dict:
    d = dict(r)
    for k in JSON_FIELDS:
        if d.get(k):
            d[k] = json.loads(d[k])
    return d


def get_call(call_id: str) -> dict | None:
    with _conn() as c:
        r = c.execute("SELECT * FROM calls WHERE call_id=?", (call_id,)).fetchone()
    return _row(r) if r else None


def list_calls(status: str | None = None) -> list[dict]:
    q, args = "SELECT * FROM calls", ()
    if status:
        q, args = q + " WHERE status=?", (status,)
    with _conn() as c:
        rows = c.execute(q + " ORDER BY updated_at DESC", args).fetchall()
    return [_row(r) for r in rows]


def latest_calls_by_invoice() -> dict[str, dict]:
    with _conn() as c:
        rows = c.execute(
            "SELECT * FROM calls WHERE invoice_id IS NOT NULL ORDER BY updated_at ASC"
        ).fetchall()
    return {r["invoice_id"]: _row(r) for r in rows}


def mark_paid(invoice_id: str):
    with _conn() as c:
        c.execute(
            "INSERT OR REPLACE INTO payments (invoice_id, paid_at) VALUES (?, ?)",
            (invoice_id, time.time()),
        )


def paid_invoice_ids() -> set[str]:
    with _conn() as c:
        rows = c.execute("SELECT invoice_id FROM payments").fetchall()
    return {r["invoice_id"] for r in rows}