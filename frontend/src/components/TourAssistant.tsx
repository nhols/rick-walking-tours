import { useEffect, useRef, useState, type FormEvent } from "react";
import { LoaderCircle, Send, Sparkles, X } from "lucide-react";
import { askTourAssistant } from "../lib/api";
import { loadTourAssistantTurns } from "../lib/assistant";
import type {
  TourAssistantInput,
  TourAssistantOutput,
  TourAssistantTurn
} from "../types";


const QUICK_QUESTIONS = [
  "Tell me more about this chapter",
  "How far away is the next stop?"
];

export function TourAssistant({
  tourId,
  selectedChapterId,
  playbackSeconds,
  onClose
}: {
  tourId: string;
  selectedChapterId: string | undefined;
  playbackSeconds: number;
  onClose: () => void;
}) {
  const [turns, setTurns] = useState<TourAssistantTurn[]>([]);
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [pendingMessage, setPendingMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let active = true;
    void loadTourAssistantTurns(tourId)
      .then((storedTurns) => {
        if (active) setTurns(storedTurns);
      })
      .catch((loadError: unknown) => {
        if (active) {
          setError(
            loadError instanceof Error ? loadError.message : "Could not load chat"
          );
        }
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [tourId]);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [loading, sending, turns]);

  useEffect(() => {
    function closeOnEscape(event: KeyboardEvent) {
      if (event.key === "Escape" && !sending) onClose();
    }
    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, [onClose, sending]);

  async function send(text: string) {
    const question = text.trim();
    if (!question || !selectedChapterId || sending) return;
    setSending(true);
    setPendingMessage(question);
    setMessage("");
    setError(null);
    try {
      const reply = await askTourAssistant(
        tourId,
        selectedChapterId,
        playbackSeconds,
        question
      );
      setTurns((current) => [
        ...current,
        { ...reply, created_at: new Date().toISOString() }
      ]);
    } catch (sendError) {
      setMessage(question);
      setError(sendError instanceof Error ? sendError.message : "Rick could not answer");
    } finally {
      setPendingMessage(null);
      setSending(false);
    }
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    void send(message);
  }

  return (
    <section
      className="tour-assistant-panel"
      role="dialog"
      aria-modal="false"
      aria-labelledby="tour-assistant-title"
    >
      <header className="tour-assistant-header">
        <span className="tour-assistant-mark"><Sparkles size={16} /></span>
        <div>
          <strong id="tour-assistant-title">Ask Rick</strong>
          <small>Your tour companion</small>
        </div>
        <button
          className="icon-button"
          type="button"
          aria-label="Close Ask Rick"
          onClick={onClose}
          disabled={sending}
        >
          <X size={18} />
        </button>
      </header>

      <div className="tour-assistant-conversation">
        <div className="assistant-bubble">
          Hi, I’m Rick. Ask me anything about this tour.
        </div>
        {loading ? (
          <div className="assistant-loading">
            <LoaderCircle className="spin" size={17} /> Loading chat…
          </div>
        ) : (
          <>
            {turns.map((turn) => (
              <div className="assistant-turn" key={`${turn.thread_id}-${turn.turn}`}>
                <div className="assistant-user-bubble">
                  {assistantText(turn.input)}
                </div>
                <div className="assistant-bubble">{assistantText(turn.output)}</div>
              </div>
            ))}
            {turns.length === 0 && !pendingMessage && (
              <div className="assistant-quick-questions">
                {QUICK_QUESTIONS.map((question) => (
                  <button
                    type="button"
                    key={question}
                    onClick={() => void send(question)}
                    disabled={sending || !selectedChapterId}
                  >
                    {question}
                  </button>
                ))}
              </div>
            )}
          </>
        )}
        {pendingMessage && (
          <div className="assistant-user-bubble">{pendingMessage}</div>
        )}
        {sending && (
          <div className="assistant-loading">
            <LoaderCircle className="spin" size={17} /> Rick is thinking…
          </div>
        )}
        {error && <p className="assistant-error">{error}</p>}
        <div ref={endRef} />
      </div>

      <form className="tour-assistant-form" onSubmit={submit}>
        <textarea
          rows={2}
          maxLength={2_000}
          aria-label="Ask Rick a question"
          placeholder="Ask about the tour…"
          value={message}
          onChange={(event) => setMessage(event.target.value)}
          disabled={loading || sending || !selectedChapterId}
        />
        <button
          type="submit"
          aria-label="Send question"
          disabled={!message.trim() || loading || sending || !selectedChapterId}
        >
          {sending ? <LoaderCircle className="spin" size={17} /> : <Send size={17} />}
        </button>
      </form>
    </section>
  );
}

function assistantText(document: TourAssistantInput | TourAssistantOutput): string {
  return document.content
    .filter((block) => block.type === "text")
    .map((block) => block.text)
    .join("\n\n");
}
