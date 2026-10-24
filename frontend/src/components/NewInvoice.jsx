import { useState } from "react";
import { createInvoice } from "../api";

const EMPTY = {
  first_name: "",
  last_name: "",
  email: "",
  description: "",
  amount: "",
  days_overdue: "10",
};

export default function NewInvoice({ onCreated }) {
  const [open, setOpen] = useState(false);
  const [f, setF] = useState(EMPTY);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });

  async function submit() {
    setBusy(true);
    setError("");
    try {
      const due = new Date(Date.now() - Number(f.days_overdue) * 86400000)
        .toISOString()
        .slice(0, 10);
      await createInvoice({
        first_name: f.first_name,
        last_name: f.last_name,
        email: f.email,
        description: f.description,
        amount: Number(f.amount),
        due_date: due,
      });
      setF(EMPTY);
      setOpen(false);
      onCreated?.();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  if (!open) {
    return (
      <button onClick={() => setOpen(true)} style={{ marginBottom: 12 }}>
        + New invoice
      </button>
    );
  }

  const ready = f.first_name && f.email && f.description && Number(f.amount) > 0;

  return (
    <div className="card">
      <h2>New invoice</h2>
      <p className="muted">Creates and sends a real invoice in your PayPal sandbox.</p>
      <div className="form-grid">
        <input placeholder="First name" value={f.first_name} onChange={set("first_name")} />
        <input placeholder="Last name" value={f.last_name} onChange={set("last_name")} />
        <input placeholder="Client email" value={f.email} onChange={set("email")} />
        <input placeholder="What it's for" value={f.description} onChange={set("description")} />
        <input placeholder="Amount (USD)" type="number" value={f.amount} onChange={set("amount")} />
        <input placeholder="Days overdue" type="number" value={f.days_overdue} onChange={set("days_overdue")} />
      </div>
      <div className="row" style={{ justifyContent: "flex-start", marginTop: 12 }}>
        <button className="primary" onClick={submit} disabled={busy || !ready}>
          {busy ? "Creating..." : "Create invoice"}
        </button>
        <button onClick={() => setOpen(false)}>Cancel</button>
      </div>
      {error && <p className="error">{error}</p>}
    </div>
  );
}