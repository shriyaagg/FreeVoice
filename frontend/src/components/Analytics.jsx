import { useEffect, useState } from "react";
import { getAnalytics } from "../api";

const LABELS = {
  promised: "Promised to pay",
  paid_now: "Paying now",
  paid: "Paid",
  needs_approval: "Needed approval",
  refused: "Refused",
  disputed: "Disputed",
  no_answer: "No answer",
};

function duration(sec) {
  if (sec == null) return "n/a";
  if (sec < 3600) return `${Math.max(1, Math.round(sec / 60))} min`;
  if (sec < 86400) return `${(sec / 3600).toFixed(1)} hours`;
  return `${(sec / 86400).toFixed(1)} days`;
}

export default function Analytics() {
  const [a, setA] = useState(null);

  useEffect(() => {
    const load = () => getAnalytics().then(setA).catch(() => {});
    load();
    const t = setInterval(load, 8000);
    return () => clearInterval(t);
  }, []);

  if (!a) return null;
  const entries = Object.entries(a.outcomes);
  const max = Math.max(1, ...entries.map(([, n]) => n));
  const p = a.promises;

  return (
    <div className="card">
      <h2>Recovery analytics</h2>
      <div className="stats" style={{ marginTop: 12 }}>
        <div className="stat">
          <span className="muted">Recovery rate</span>
          <b>{a.recovery_rate == null ? "n/a" : `${a.recovery_rate}%`}</b>
          <span className="muted">
            {a.paid} of {a.contacted} contacted invoices paid
          </span>
        </div>
        <div className="stat">
          <span className="muted">Recovered after calls</span>
          <b>${Math.round(a.recovered_amount).toLocaleString()}</b>
        </div>
        <div className="stat">
          <span className="muted">Avg time to pay</span>
          <b>{duration(a.avg_seconds_to_pay)}</b>
          <span className="muted">after first call</span>
        </div>
        <div className="stat">
          <span className="muted">Promises</span>
          <b>
            {p.kept} kept · {p.broken} broken
          </b>
          <span className="muted">{p.pending} pending</span>
        </div>
      </div>

      {entries.length > 0 && (
        <div className="bars">
          <p className="muted">How calls ended</p>
          {entries.map(([k, n]) => (
            <div key={k} className="bar-row">
              <span>{LABELS[k] || k}</span>
              <div className="bar-track">
                <div className="bar-fill" style={{ width: `${(n / max) * 100}%` }} />
              </div>
              <b>{n}</b>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}