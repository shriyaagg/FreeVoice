import { useEffect, useRef, useState } from "react";
import { getPublicCall, sendMessage } from "./api";
import { useSpeech } from "./hooks/useSpeech";

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
    setAnswered(true);
    try {
      await sync();
    } catch (e) {
      setError(e.message);
    }
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

  const done = call?.status === "done";

  return (
    <div className="phone-wrap">
      <div className="phone">
        <div className="phone-head">
          <h1>{answered ? "On call" : done ? "Call ended" : "Incoming call"}</h1>
          <p className="muted">
            Payment assistant, calling for your freelancer
            {call ? ` about invoice ${call.invoice_number}` : ""}
          </p>
        </div>

        {error && <p className="error">{error}</p>}

        {!answered && call && !done && (
          <button className="answer" onClick={answer}>
            Answer
          </button>
        )}

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

            {call?.status === "awaiting_owner" && (
              <div className="banner">Please hold, the assistant is checking something...</div>
            )}
            {done && (
              <div className="banner ok">
                Call ended
                {call.promise_date ? ` · payment promised for ${call.promise_date}` : ""}
              </div>
            )}

            {call?.status === "awaiting_client" && (
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

        {!answered && done && (
          <div className="banner ok">This call has already ended.</div>
        )}
      </div>
    </div>
  );
}