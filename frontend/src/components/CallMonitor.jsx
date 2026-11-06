import { useEffect, useState } from "react";
import { expirePromise, getCall, getHealth, startCall } from "../api";

const CHIPS = {
  ringing: ["Ringing the client...", ""],
  missed: ["No answer, will retry", "wait"],
  unreachable: ["Unreachable, reminder sent", ""],
  awaiting_client: ["Live: talking to the client", ""],
  awaiting_owner: ["Needs your decision", "wait"],
  done: ["Call finished", ""],
};
const LIVE = ["ringing", "missed", "awaiting_client", "awaiting_owner"];

export default function CallMonitor({ invoice, onChange }) {
  const [call, setCall] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [copied, setCopied] = useState(false);
  const [demo, setDemo] = useState(false);

  const callId = invoice?.last_call_id || null;

  useEffect(() => {
    getHealth().then((h) => setDemo(!!h.demo_mode)).catch(() => {});
  }, []);

  useEffect(() => {
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
      await startCall(invoice.id);
      await onChange?.();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  async function fastForward() {
    try {
      await expirePromise(invoice.id);
      await onChange?.();
    } catch (e) {
      setError(e.message);
    }
  }

  const link = callId ? `${window.location.origin}/call/${callId}` : "";
  const live = call && LIVE.includes(call.status);
  const disputed = call?.outcome === "disputed";
  const chip = call ? CHIPS[call.status] : null;
  const canStart = invoice && !invoice.paid && !live && !disputed;

  return (
    <div className="card">
      <h2>Call monitor</h2>

      {!invoice && <p className="muted">Open an invoice in the table to call its client.</p>}
      {invoice && (
        <p className="muted">
          Invoice {invoice.number} · {invoice.client_name} · {invoice.amount} {invoice.currency}
        </p>
      )}

      {canStart && (
        <button className="primary" onClick={start} disabled={busy}>
          {busy ? "Starting..." : call ? "Start new call" : "Start call"}
        </button>
      )}
      {invoice?.paid && <div className="banner ok">This invoice has been paid.</div>}
      {disputed && (
        <div className="banner">
          Under dispute: {call.dispute_reason || "no reason given"}. Collection is paused
          until you resolve it.
        </div>
      )}

      {live && (
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

      {chip && (
        <span className={`chip ${chip[1]}`}>
          {call.kind === "follow_up" ? "Follow-up · " : ""}
          {chip[0]}
          {["ringing", "missed"].includes(call.status) && call.attempts > 1
            ? ` (attempt ${call.attempts})`
            : ""}
        </span>
      )}

      {call?.summary && (
        <div className="banner ok">
          <b>Summary:</b> {call.summary}
        </div>
      )}

      {demo && call?.status === "done" && call.outcome === "promised" && (
        <div>
          <button onClick={fastForward}>Demo: the promised date passes</button>
        </div>
      )}

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
      {error && <p className="error">{error}</p>}
    </div>
  );
}