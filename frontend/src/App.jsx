import { useCallback, useEffect, useState } from "react";
import { getDashboard } from "./api";
import ApprovalQueue from "./components/ApprovalQueue";
import InvoiceGrid from "./components/InvoiceGrid";
import CallMonitor from "./components/CallMonitor";

const OPEN = ["SENT", "UNPAID", "PARTIALLY_PAID"];
const money = (n) =>
  `$${n.toLocaleString(undefined, { maximumFractionDigits: 0 })}`;

export default function App() {
  const [rows, setRows] = useState([]);
  const [selected, setSelected] = useState(null);
  const [error, setError] = useState("");

  const refresh = useCallback(async () => {
    try {
      setRows(await getDashboard());
      setError("");
    } catch (e) {
      setError(e.message);
    }
  }, []);

  useEffect(() => {
    refresh();
    const t = setInterval(refresh, 6000);
    return () => clearInterval(t);
  }, [refresh]);

  const open = rows.filter(
    (r) => !r.paid && r.days_overdue > 0 && OPEN.includes(r.status)
  );
  const outstanding = open.reduce((a, r) => a + parseFloat(r.amount || 0), 0);
  const recovered = rows
    .filter((r) => r.paid)
    .reduce((a, r) => a + parseFloat(r.total || 0), 0);
  const promised = rows.filter((r) => r.promise_date && !r.paid).length;

  return (
    <div className="app">
      <header>
        <h1>Collections agent</h1>
        <p className="muted">
          An AI assistant that chases overdue PayPal invoices, within limits you set.
        </p>
      </header>

      <div className="stats">
        <div className="stat"><span className="muted">Overdue</span><b>{open.length}</b></div>
        <div className="stat"><span className="muted">Outstanding</span><b>{money(outstanding)}</b></div>
        <div className="stat"><span className="muted">Promised to pay</span><b>{promised}</b></div>
        <div className="stat"><span className="muted">Recovered</span><b>{money(recovered)}</b></div>
      </div>

      {error && <p className="error">Backend error: {error}</p>}

      <div className="card">
        <InvoiceGrid rows={rows} selectedId={selected?.id} onCall={setSelected} />
      </div>

      <div className="cols">
        <CallMonitor invoice={selected} onChange={refresh} />
        <ApprovalQueue onChange={refresh} />
      </div>
    </div>
  );
}