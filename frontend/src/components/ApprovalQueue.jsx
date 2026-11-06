import { useEffect, useState } from "react";
import { decide, getCalls, resolveDispute } from "../api";

function label(r) {
  if (!r) return "Unknown request";
  if (r.type === "extension_days") return `Extension of ${r.value} days`;
  if (r.type === "discount_percent") return `${r.value}% discount`;
  return "Unspecified request";
}

export default function ApprovalQueue({ onChange }) {
  const [items, setItems] = useState([]);
  const [disputes, setDisputes] = useState([]);
  const [busy, setBusy] = useState(null);

  async function load() {
    try {
      const [a, d] = await Promise.all([
        getCalls("awaiting_owner"),
        getCalls(null, "disputed"),
      ]);
      setItems(a);
      setDisputes(d);
    } catch {
      /* backend may be restarting */
    }
  }

  useEffect(() => {
    load();
    const t = setInterval(load, 3000);
    return () => clearInterval(t);
  }, []);

  async function act(fn, id) {
    setBusy(id);
    try {
      await fn();
      await load();
      onChange?.();
    } catch (e) {
      alert(e.message);
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="card">
      <h2>Freelancer approvals</h2>
      {items.length === 0 && disputes.length === 0 && (
        <p className="muted">Nothing waiting for the freelancer.</p>
      )}

      {items.map((c) => (
        <div key={c.call_id} className="approval">
          <b>
            {c.client_name} · invoice {c.invoice_number}
          </b>
          <div>{label(c.approval?.request)}</div>
          <div className="muted">Outside your policy limits.</div>
          <div className="actions">
            <button
              className="approve"
              disabled={busy === c.call_id}
              onClick={() => act(() => decide(c.call_id, true), c.call_id)}
            >
              Approve
            </button>
            <button
              className="danger"
              disabled={busy === c.call_id}
              onClick={() => act(() => decide(c.call_id, false), c.call_id)}
            >
              Deny
            </button>
          </div>
        </div>
      ))}

      {disputes.length > 0 && <p className="muted">Disputed invoices (collection paused)</p>}
      {disputes.map((c) => (
        <div key={c.call_id} className="approval dispute">
          <b>
            {c.client_name} · invoice {c.invoice_number}
          </b>
          <div>{c.dispute_reason || "No reason given"}</div>
          <div className="actions">
            <button
              disabled={busy === c.call_id}
              onClick={() => act(() => resolveDispute(c.call_id), c.call_id)}
            >
              Mark resolved
            </button>
          </div>
        </div>
      ))}
    </div>
  );
}