import { useEffect, useState } from "react";
import { getCall, startCall } from "../api";

const CHIPS = {
  awaiting_client: ["Live: talking to the client", ""],
  awaiting_owner: ["Needs your decision", "wait"],
  done: ["Call finished", ""],
};

export default function CallMonitor({ invoice, onChange }) {
  const [startedId, setStartedId] = useState(null);
  const [call, setCall] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [copied, setCopied] = useState(false);

  const callId = startedId || invoice?.last_call_id || null;

  useEffect(() => {
    setStartedId(null);
    setCall(null);
    setError("");
  }, [invoice?.id]);

  useEffect(() => {
    if (!callId) {
      setCall(null);
      return;
    }
    let alive = true;
    const load = () =>
      getCall(callId)
        .then((c) => alive && setCall(c))
        .catch(() => {});
    load();
    const t = setInterval(load, 2500);
    return () => {
      alive = false;
      clearInterval(t);
    };
  }, [callId]);

  async function start() {
    setBusy(true);
    setError("");
    try {
      const res = await startCall(invoice.id);
      setStartedId(res.call_id);
      onChange?.();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  const link = callId ? `${window.location.origin}/call/${callId}` : "";
  const active = call && ["awaiting_client", "awaiting_owner"].includes(call.status);
  const chip = call ? CHIPS[call.status] : null;

  return (
    <div className="card">
      <h2>Call monitor</h2>

      {!invoice && <p className="muted">Open an invoice in the table to call its client.</p>}

      {invoice && (
        <p className="muted">
          Invoice {invoice.number} · {invoice.client_name} · {invoice.amount} {invoice.currency}
        </p>
      )}

      {invoice && !active && (
        <button className="primary" onClick={start} disabled={busy || invoice.paid}>
          {invoice.paid ? "Already paid" : busy ? "Starting..." : call ? "Start new call" : "Start call"}
        </button>
      )}

      {active && (
        <>
          <p className="muted">Send this link to the client. They take the call there.</p>
          <div className="link-box">
            <input readOnly value={link} />
            <button
              onClick={() => {
                navigator.clipboard.writeText(link);
                setCopied(true);
                setTimeout(() => setCopied(false), 1500);
              }}
            >
              {copied ? "Copied" : "Copy"}
            </button>
            <a className="btnlink" href={link} target="_blank" rel="noreferrer">
              Open as client
            </a>
          </div>
        </>
      )}

      {chip && <span className={`chip ${chip[1]}`}>{chip[0]}</span>}

      {call?.transcript?.length > 0 && (
        <>
          <p className="muted">Live transcript (read only)</p>
          <div className="chat">
            {call.transcript.map((m, i) => (
              <div key={i} className={`bubble ${m.role}`}>
                {m.text}
              </div>
            ))}
          </div>
        </>
      )}

      {call?.status === "done" && (
        <div className="banner ok">
          Outcome: {call.outcome}
          {call.promise_date ? ` · promise ${call.promise_date}` : ""}
        </div>
      )}
      {error && <p className="error">{error}</p>}
    </div>
  );
}