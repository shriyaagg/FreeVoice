import { useEffect, useState } from "react";
import { decide, getCalls } from "../api";

function label(r) {
  if (!r) return "Unknown request";
  if (r.type === "extension_days") return `Extension of ${r.value} days`;
  if (r.type === "discount_percent") return `${r.value}% discount`;
  return "Unspecified request";
}

export default function ApprovalQueue({ onChange }) {
  const [items, setItems] = useState([]);
  const [busy, setBusy] = useState(null);

  async function load() {
    try {
      setItems(await getCalls("awaiting_owner"));
    } catch {
      /* backend may be restarting */
    }
  }

  useEffect(() => {
    load();
    const t = setInterval(load, 3000);
    return () => clearInterval(t);
  }, []);

  async function act(id, approved) {
    setBusy(id);
    try {
      await decide(id, approved);
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
      <h2>Owner approvals</h2>
      {items.length === 0 && <p className="muted">Nothing waiting for you.</p>}
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
              onClick={() => act(c.call_id, true)}
            >
              Approve
            </button>
            <button
              className="danger"
              disabled={busy === c.call_id}
              onClick={() => act(c.call_id, false)}
            >
              Deny
            </button>
          </div>
        </div>
      ))}
    </div>
  );
}