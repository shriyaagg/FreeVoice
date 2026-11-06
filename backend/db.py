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
                status TEXT, outcome TEXT, kind TEXT,
                promise_date TEXT, promise_result TEXT,
                approval TEXT, owner_decision TEXT, escalation TEXT,
                dispute_reason TEXT, summary TEXT, transcript TEXT,
                attempts INTEGER, ring_started_at REAL, next_ring_at REAL,
                created_at REAL, updated_at REAL
            )"""
        )
        c.execute(
            "CREATE TABLE IF NOT EXISTS payments (invoice_id TEXT PRIMARY KEY, paid_at REAL)"
        )


def save_call(call_id: str, **fields):
    now = time.time()
    fields["updated_at"] = now
    for k in JSON_FIELDS:
        if fields.get(k) is not None:
            fields[k] = json.dumps(fields[k])
    cols = ["call_id", "created_at", *fields]
    vals = [call_id, now, *fields.values()]
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


def list_calls(status: str | None = None, outcome: str | None = None) -> list[dict]:
    clauses, args = [], []
    if status:
        clauses.append("status=?")
        args.append(status)
    if outcome:
        clauses.append("outcome=?")
        args.append(outcome)
    q = "SELECT * FROM calls"
    if clauses:
        q += " WHERE " + " AND ".join(clauses)
    with _conn() as c:
        rows = c.execute(q + " ORDER BY updated_at DESC", args).fetchall()
    return [_row(r) for r in rows]


def calls_for_invoice(invoice_id: str) -> list[dict]:
    with _conn() as c:
        rows = c.execute(
            "SELECT * FROM calls WHERE invoice_id=? ORDER BY created_at ASC",
            (invoice_id,),
        ).fetchall()
    return [_row(r) for r in rows]


def count_calls(invoice_id: str, outcome: str) -> int:
    with _conn() as c:
        return c.execute(
            "SELECT COUNT(*) FROM calls WHERE invoice_id=? AND outcome=?",
            (invoice_id, outcome),
        ).fetchone()[0]


def latest_calls_by_invoice() -> dict[str, dict]:
    with _conn() as c:
        rows = c.execute(
            "SELECT * FROM calls WHERE invoice_id IS NOT NULL ORDER BY created_at ASC"
        ).fetchall()
    return {r["invoice_id"]: _row(r) for r in rows}


def mark_paid(invoice_id: str):
    with _conn() as c:
        c.execute(
            "INSERT OR IGNORE INTO payments (invoice_id, paid_at) VALUES (?, ?)",
            (invoice_id, time.time()),
        )


def paid_invoice_ids() -> set[str]:
    with _conn() as c:
        rows = c.execute("SELECT invoice_id FROM payments").fetchall()
    return {r["invoice_id"] for r in rows}


def paid_times() -> dict[str, float]:
    with _conn() as c:
        rows = c.execute("SELECT invoice_id, paid_at FROM payments").fetchall()
    return {r["invoice_id"]: r["paid_at"] for r in rows}