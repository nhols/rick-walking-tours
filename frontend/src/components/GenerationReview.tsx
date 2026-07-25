import { lazy, useEffect, useState, type FormEvent } from "react";
import {
  Check,
  CircleAlert,
  LoaderCircle,
  MessageCircle,
  RefreshCw,
  Send
} from "lucide-react";
import { approveTour, reviseTour } from "../lib/api";
import { ACTIVE_STATUSES, STATUS_LABELS, type TourBundle } from "../types";


const CheckpointMap = lazy(() => import("./CheckpointMap"));

export function GenerationReview({
  bundle,
  onChanged
}: {
  bundle: TourBundle;
  onChanged: () => Promise<void>;
}) {
  const currentPlan = bundle.plans.at(-1);
  const [selectedPlanId, setSelectedPlanId] = useState(currentPlan?.id);
  const [selectedCheckpointId, setSelectedCheckpointId] = useState<string>();
  const [feedback, setFeedback] = useState("");
  const [busy, setBusy] = useState<"approve" | "feedback" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const selectedPlan =
    bundle.plans.find((plan) => plan.id === selectedPlanId) ?? currentPlan;
  const canReview = bundle.tour.status === "awaiting_review" && currentPlan;
  const latestError = bundle.statusEvents.at(-1)?.details?.error;

  useEffect(() => {
    setSelectedPlanId(currentPlan?.id);
    setSelectedCheckpointId(currentPlan?.payload.checkpoints[0]?.id);
  }, [currentPlan?.id]);

  async function approve() {
    if (!currentPlan) return;
    setBusy("approve");
    setError(null);
    try {
      await approveTour(bundle.tour.id, currentPlan.id);
      await onChanged();
    } catch (approveError) {
      setError(approveError instanceof Error ? approveError.message : "Approval failed");
    } finally {
      setBusy(null);
    }
  }

  async function submitFeedback(event: FormEvent) {
    event.preventDefault();
    if (!currentPlan || !feedback.trim()) return;
    setBusy("feedback");
    setError(null);
    try {
      await reviseTour(bundle.tour.id, currentPlan.id, feedback.trim());
      setFeedback("");
      await onChanged();
    } catch (feedbackError) {
      setError(feedbackError instanceof Error ? feedbackError.message : "Feedback failed");
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="review-layout">
      <section className="revision-column">
        <div className={`progress-card ${bundle.tour.status === "failed" ? "failed" : ""}`}>
          {ACTIVE_STATUSES.includes(bundle.tour.status) ? (
            <LoaderCircle className="spin" size={21} />
          ) : bundle.tour.status === "failed" ? (
            <CircleAlert size={21} />
          ) : (
            <MessageCircle size={21} />
          )}
          <div>
            <strong>{STATUS_LABELS[bundle.tour.status]}</strong>
            <span>{latestError ?? "Your plan is ready."}</span>
          </div>
        </div>
        <div className="conversation">
          <div className="message user-message">
            <small>You</small><p>{bundle.tour.input.request}</p>
          </div>
          {bundle.plans.map((plan) => (
            <div className="revision-thread" key={plan.id}>
              {plan.feedback && (
                <div className="message user-message">
                  <small>You · feedback</small><p>{plan.feedback}</p>
                </div>
              )}
              <button
                className={`message agent-message ${selectedPlan?.id === plan.id ? "selected" : ""}`}
                onClick={() => {
                  setSelectedPlanId(plan.id);
                  setSelectedCheckpointId(plan.payload.checkpoints[0]?.id);
                }}
              >
                <small>Tour plan · revision {plan.revision}</small>
                <strong>{plan.payload.narrative_arc}</strong>
                <span>{plan.payload.checkpoints.length} checkpoints · View plan</span>
              </button>
            </div>
          ))}
          {ACTIVE_STATUSES.includes(bundle.tour.status) && (
            <div className="message agent-thinking">
              <LoaderCircle className="spin" size={16} />Generating revision…
            </div>
          )}
        </div>
        {canReview && (
          <form className="feedback-form" onSubmit={submitFeedback}>
            <label htmlFor="feedback">What should change?</label>
            <div className="feedback-input">
              <textarea
                id="feedback"
                rows={3}
                placeholder="Add a stop about industrial history…"
                value={feedback}
                onChange={(event) => setFeedback(event.target.value)}
                disabled={Boolean(busy)}
              />
              <button
                className="send-button"
                disabled={!feedback.trim() || Boolean(busy)}
                title="Send feedback"
              >
                {busy === "feedback" ? (
                  <LoaderCircle className="spin" size={18} />
                ) : (
                  <Send size={18} />
                )}
              </button>
            </div>
            <button
              className="approve-button"
              type="button"
              onClick={() => void approve()}
              disabled={Boolean(busy)}
            >
              {busy === "approve" ? (
                <LoaderCircle className="spin" size={18} />
              ) : (
                <Check size={18} />
              )}
              Approve this plan and create tour
            </button>
          </form>
        )}
        {error && <p className="form-message padded">{error}</p>}
      </section>
      <section className="plan-column">
        {selectedPlan ? (
          <>
            <div className="plan-map">
              <CheckpointMap
                checkpoints={selectedPlan.payload.checkpoints}
                selectedId={selectedCheckpointId}
                onSelect={setSelectedCheckpointId}
              />
            </div>
            <div className="plan-summary">
              <p className="section-label">
                Revision {selectedPlan.revision} · chapter briefs
              </p>
              <h2>{selectedPlan.payload.narrative_arc}</h2>
              <div className="brief-list">
                {selectedPlan.payload.checkpoints.map((checkpoint) => (
                  <button
                    className={selectedCheckpointId === checkpoint.id ? "active" : ""}
                    key={checkpoint.id}
                    onClick={() => setSelectedCheckpointId(checkpoint.id)}
                  >
                    <span className="number-dot">{checkpoint.position}</span>
                    <span>
                      <strong>{checkpoint.title}</strong>
                      <small>{checkpoint.description}</small>
                    </span>
                  </button>
                ))}
              </div>
            </div>
          </>
        ) : (
          <div className="plan-empty">
            <RefreshCw className="spin-slow" />
            <h2>Generating tour plan</h2>
            <p>Checkpoints will appear when the plan is ready.</p>
          </div>
        )}
      </section>
    </div>
  );
}
