import { useEffect, useRef, useState } from "react";
import { answerCall, getPublicCall, sendMessage } from "./api";
import { useSpeech } from "./hooks/useSpeech";

const WAITING = ["ringing", "missed"];

export default function ClientCall({ callId }) {
  const { supported, listening, speak, listen, stop } = useSpeech();
  const [call, setCall] = useState(null);
  const [answered, setAnswered] = useState(false);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [voice, setVoice] = useState(supported);
  const seen = useRef(0);
  const voiceRef = useRef(supported);
  const endRef = useRef(null);

  useEffect(() => {
    voiceRef.current = voice;
  }, [voice]);

  useEffect(() => {
    getPublicCall(callId).then(setCall).catch((e) => setError(e.message));
  }, [callId]);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [call]);

  useEffect(() => {
    if (answered || !WAITING.includes(call?.status)) return;
    const t = setInterval(
      () => getPublicCall(callId).then(setCall).catch(() => {}),
      2000
    );
    return () => clearInterval(t);
  }, [answered, call?.status, callId]);

  useEffect(() => {
    if (!answered || call?.status !== "awaiting_owner") return;
    const t = setInterval(() => sync().catch(() => {}), 2500);
    return () => clearInterval(t);
  }, [answered, call?.status]);

  async function sync() {
    const c = await getPublicCall(callId);
    const transcript = c.transcript || [];
    const fresh = transcript
      .slice(seen.current)
      .filter((m) => m.role === "agent")
      .map((m) => m.text)
      .join(" ");
    seen.current = transcript.length;
    setCall(c);
    if (fresh && voiceRef.current) {
      speak(fresh, () => {
        if (c.status === "awaiting_client" && voiceRef.current) {
          listen((t) => send(t));
        }
      });
    }
  }

  async function answer() {
    setBusy(true);
    setError("");
    try {
      await answerCall(callId);
      setAnswered(true);
      seen.current = 0;
      await sync();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  async function rejoin() {
    const c = await getPublicCall(callId);
    seen.current = (c.transcript || []).length;
    setCall(c);
    setAnswered(true);
  }

  async function send(msg) {
    if (!msg?.trim()) return;
    setBusy(true);
    setError("");
    setText("");
    try {
      await sendMessage(callId, msg.trim());
      await sync();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  const status = call?.status;
  const done = status === "done";
  const waiting = WAITING.includes(status);
  const inProgress = ["awaiting_client", "awaiting_owner"].includes(status);

  const title = answered
    ? "On call"
    : status === "ringing"
    ? "Incoming call"
    : status === "missed"
    ? "Missed call"
    : status === "unreachable"
    ? "We couldn't reach you"
    : done
    ? "Call ended"
    : "Payment assistant";

  return (
    <div className="phone-wrap">
      <div className="phone">
        <div className="phone-head">
          <h1>{title}</h1>
          <p className="muted">
            Payment assistant, calling for your freelancer
            {call ? ` about invoice ${call.invoice_number}` : ""}
          </p>
        </div>

        {error && <p className="error">{error}</p>}

        {!answered && waiting && (
          <>
            {status === "missed" && (
              <div className="banner">
                You missed a call (attempt {call.attempts}). We'll try again shortly,
                or you can call back now.
              </div>
            )}
            <button
              className={`answer ${status === "ringing" ? "ringing" : ""}`}
              onClick={answer}
              disabled={busy}
            >
              {status === "ringing" ? "Answer" : "Call back"}
            </button>
          </>
        )}

        {!answered && inProgress && (
          <button className="answer" onClick={rejoin}>
            Rejoin call
          </button>
        )}

        {!answered && status === "unreachable" && (
          <div className="banner">
            We tried a few times and couldn't reach you. A payment reminder was
            sent to your email.
          </div>
        )}

        {!answered && done && <div className="banner ok">This call has already ended.</div>}

        {answered && (
          <>
            <label className="muted">
              <input
                type="checkbox"
                checked={voice}
                disabled={!supported}
                onChange={(e) => setVoice(e.target.checked)}
              />{" "}
              Voice
            </label>

            <div className="chat">
              {call?.transcript?.map((m, i) => (
                <div key={i} className={`bubble ${m.role}`}>
                  {m.text}
                </div>
              ))}
              <div ref={endRef} />
            </div>

            {status === "awaiting_owner" && (
              <div className="banner">Please hold, the assistant is checking with the freelancer...</div>            )}
            {done && (
              <div className="banner ok">
                Call ended
                {call.promise_date ? ` · payment promised for ${call.promise_date}` : ""}
              </div>
            )}

            {status === "awaiting_client" && (
              <div className="row">
                <input
                  type="text"
                  value={text}
                  placeholder="Type your reply..."
                  onChange={(e) => setText(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && send(text)}
                />
                <button onClick={() => send(text)} disabled={busy}>
                  Send
                </button>
                {supported && (
                  <button onClick={() => (listening ? stop() : listen((t) => send(t)))}>
                    {listening ? "Stop" : "Mic"}
                  </button>
                )}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}