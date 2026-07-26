import { lazy, useEffect, useState, type FormEvent } from "react";
import {
  Check,
  CircleAlert,
  Coins,
  LoaderCircle,
  MessageCircle,
  Send
} from "lucide-react";
import { approveTour, reviseTour } from "../lib/api";
import {
  ACTIVE_STATUSES,
  STATUS_LABELS,
  type TourBundle,
  type TourStatus
} from "../types";


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
  const [showApprovalDialog, setShowApprovalDialog] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const selectedPlan =
    bundle.plans.find((plan) => plan.id === selectedPlanId) ?? currentPlan;
  const canReview = bundle.tour.status === "awaiting_review" && currentPlan;
  const latestError = bundle.statusEvents.at(-1)?.details?.error;
  const isActive = ACTIVE_STATUSES.includes(bundle.tour.status);
  const statusMessage = getStatusMessage(bundle.tour.status, bundle.plans.length > 0);

  useEffect(() => {
    setSelectedPlanId(currentPlan?.id);
    setSelectedCheckpointId(currentPlan?.payload.checkpoints[0]?.id);
  }, [currentPlan?.id]);

  useEffect(() => {
    if (!showApprovalDialog) return;

    function closeOnEscape(event: KeyboardEvent) {
      if (event.key === "Escape" && !busy) setShowApprovalDialog(false);
    }

    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, [showApprovalDialog, busy]);

  async function approve() {
    if (!currentPlan) return;
    setBusy("approve");
    setError(null);
    try {
      await approveTour(bundle.tour.id, currentPlan.id);
      setShowApprovalDialog(false);
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
    <>
      <div className="review-layout">
        <section className="revision-column">
        <div className={`progress-card ${bundle.tour.status === "failed" ? "failed" : ""}`}>
          {isActive ? (
            <LoaderCircle className="spin" size={21} />
          ) : bundle.tour.status === "failed" ? (
            <CircleAlert size={21} />
          ) : (
            <MessageCircle size={21} />
          )}
          <div>
            <strong>{STATUS_LABELS[bundle.tour.status]}</strong>
            <span>{latestError ?? statusMessage}</span>
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
                <p className="narrative-summary">{plan.payload.narrative_arc}</p>
                <span>{plan.payload.checkpoints.length} checkpoints · View plan</span>
              </button>
              {bundle.tour.approved_plan_id === plan.id && (
                <div className="message user-message approval-message">
                  <small>You · approval</small>
                  <p><Check size={16} />Approved this plan</p>
                </div>
              )}
            </div>
          ))}
          {isActive && (
            <div className="message agent-thinking">
              {getActivityMessage(bundle.tour.status, bundle.plans.length > 0)}
            </div>
          )}
        </div>
        {canReview && (
          <form className="feedback-form" onSubmit={submitFeedback}>
            <p className="review-decision-heading">Choose what happens next</p>
            <div className="review-action review-feedback-action">
              <div className="review-action-heading">
                <span className="review-action-icon"><MessageCircle size={14} /></span>
                <div>
                  <label htmlFor="feedback">Request changes</label>
                  <p>Tell us what to revise and we’ll update the plan.</p>
                </div>
              </div>
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
                >
                  {busy === "feedback" ? (
                    <LoaderCircle className="spin" size={18} />
                  ) : (
                    <Send size={18} />
                  )}
                  Send feedback
                </button>
              </div>
            </div>
            <div className="review-choice" aria-hidden="true"><span>or</span></div>
            <div className="review-action review-approval-action">
              <div className="review-action-heading">
                <span className="review-action-icon"><Check size={14} /></span>
                <div>
                  <strong>Approve the tour</strong>
                  <p>Happy with the plan? Approve it to create the full tour.</p>
                </div>
              </div>
              <button
                className="approve-button"
                type="button"
                onClick={() => {
                  setError(null);
                  setShowApprovalDialog(true);
                }}
                disabled={Boolean(busy)}
              >
                <Check size={18} />
                Approve tour
                <span>1 credit</span>
              </button>
            </div>
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
              <p className="narrative-summary">{selectedPlan.payload.narrative_arc}</p>
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
            <h2>{STATUS_LABELS[bundle.tour.status]}</h2>
            <p>Checkpoints will appear when the plan is ready.</p>
          </div>
        )}
        </section>
      </div>
      {showApprovalDialog && (
        <div
          className="dialog-backdrop"
          role="presentation"
          onMouseDown={(event) =>
            event.target === event.currentTarget && !busy && setShowApprovalDialog(false)
          }
        >
          <form
            className="dialog confirmation-dialog"
            role="dialog"
            aria-modal="true"
            aria-labelledby="approval-dialog-title"
            aria-describedby="approval-dialog-description"
            onSubmit={(event) => {
              event.preventDefault();
              void approve();
            }}
          >
            <div className="confirmation-icon"><Coins size={24} /></div>
            <h2 id="approval-dialog-title">Approve and create this tour?</h2>
            <p id="approval-dialog-description">
              This will approve the current plan and start creating your full tour.
            </p>
            <div className="credit-warning">
              <Coins size={20} />
              <div>
                <strong>This action uses 1 credit</strong>
                <span>The credit will be used when you confirm.</span>
              </div>
            </div>
            {error && <p className="form-message">{error}</p>}
            <div className="dialog-actions">
              <button
                className="secondary-button"
                type="button"
                onClick={() => setShowApprovalDialog(false)}
                disabled={Boolean(busy)}
                autoFocus
              >
                Keep reviewing
              </button>
              <button className="primary-button" disabled={Boolean(busy)}>
                {busy === "approve" ? (
                  <LoaderCircle className="spin" size={18} />
                ) : (
                  <Check size={18} />
                )}
                Yes, approve · 1 credit
              </button>
            </div>
          </form>
        </div>
      )}
    </>
  );
}

function getStatusMessage(status: TourStatus, hasPlan: boolean): string {
  switch (status) {
    case "researching":
      return hasPlan
        ? "Applying your feedback to a new plan."
        : "Finding the best stops and route.";
    case "awaiting_review":
      return "Review the plan, request changes, or approve it.";
    case "writing_chapters":
      return "Turning your approved plan into narrated chapters.";
    case "generating_audio":
      return "The chapters are ready; their audio is being generated.";
    case "ready":
      return "Your tour is ready.";
    case "failed":
      return "Something went wrong while creating the tour.";
  }
}

function getActivityMessage(status: TourStatus, hasPlan: boolean): string {
  switch (status) {
    case "researching":
      return hasPlan ? "Revising your tour plan…" : "Researching checkpoints…";
    case "writing_chapters":
      return "Writing your tour chapters…";
    case "generating_audio":
      return "Generating chapter audio…";
    default:
      return getStatusMessage(status, hasPlan);
  }
}
