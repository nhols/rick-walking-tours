import { useEffect, useState } from "react";
import { Check, CircleCheckBig, Footprints, Star, X } from "lucide-react";
import { markTourCompleted, unmarkTourCompleted } from "../lib/completions";
import { loadTourReview, saveTourReview } from "../lib/reviews";
import type { Tour } from "../types";

const DEFAULT_REVIEWS = [
  "I came, I saw, I wandered.",
  "Rick-ommended!",
  "Right up my street.",
  "Worth every step."
];

function randomDefaultReview(): string {
  return DEFAULT_REVIEWS[Math.floor(Math.random() * DEFAULT_REVIEWS.length)];
}

export function CompletionDialog({
  tour,
  viewerId,
  onClose,
  onCompleted
}: {
  tour: Tour;
  viewerId: string;
  onClose: () => void;
  onCompleted: () => Promise<void>;
}) {
  const [rating, setRating] = useState(0);
  const [body, setBody] = useState(randomDefaultReview);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const isCompleted = Boolean(tour.completed_at);
  const [reviewReady, setReviewReady] = useState(isCompleted);

  useEffect(() => {
    if (isCompleted) return;
    let active = true;
    setReviewReady(false);
    void loadTourReview(tour.id, viewerId)
      .then((review) => {
        if (!active) return;
        if (review) {
          setRating(review.rating);
          setBody(review.body);
        }
        setReviewReady(true);
      })
      .catch(() => {
        if (active) setError("Could not load your existing review.");
      });
    return () => {
      active = false;
    };
  }, [isCompleted, tour.id, viewerId]);

  async function complete() {
    if (rating && !body.trim()) {
      setError("Write a short review or clear the star rating.");
      return;
    }

    setSaving(true);
    setError(null);
    try {
      if (rating) {
        await saveTourReview(tour.id, viewerId, rating, body.trim());
      } else {
        await markTourCompleted(tour.id);
      }
      await onCompleted();
      onClose();
    } catch (completionError) {
      setError(
        completionError instanceof Error
          ? completionError.message
          : "Could not mark this tour completed"
      );
    } finally {
      setSaving(false);
    }
  }

  async function uncomplete() {
    setSaving(true);
    setError(null);
    try {
      await unmarkTourCompleted(tour.id);
      await onCompleted();
      onClose();
    } catch (completionError) {
      setError(
        completionError instanceof Error
          ? completionError.message
          : "Could not remove the completed status"
      );
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="dialog-backdrop completion-dialog-backdrop" role="presentation">
      <section
        className="dialog completion-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="completion-title"
      >
        <header className="completion-dialog-header">
          <span className="confirmation-icon">
            {isCompleted ? <CircleCheckBig size={23} /> : <Footprints size={23} />}
          </span>
          <button
            className="icon-button"
            type="button"
            onClick={onClose}
            disabled={saving}
            aria-label="Close"
          >
            <X size={20} />
          </button>
        </header>
        {isCompleted ? (
          <>
            <h2 id="completion-title">Are you sure?</h2>
            <p>
              Remove the completed status from <strong>{tour.title ?? tour.input.location}</strong>?
              Any review you left will remain.
            </p>
            {error && <p className="form-message">{error}</p>}
            <div className="dialog-actions">
              <button
                className="primary-button"
                type="button"
                onClick={() => void uncomplete()}
                disabled={saving}
              >
                {saving ? "Saving…" : "Remove completed status"}
              </button>
            </div>
          </>
        ) : (
          <>
            <h2 id="completion-title">Complete this walk?</h2>
            <p>
              Mark <strong>{tour.title ?? tour.input.location}</strong> as completed.
            </p>

            <div className="completion-review-fields">
              <div className="completion-review-heading">
                <strong>Leave a review</strong>
                <small>Optional — choose a rating to post it</small>
              </div>
              <div className="star-picker" aria-label="Star rating">
                {[1, 2, 3, 4, 5].map((value) => (
                  <button
                    type="button"
                    key={value}
                    className={value <= rating ? "selected" : ""}
                    disabled={!reviewReady}
                    onClick={() => {
                      setRating(rating === value ? 0 : value);
                      setError(null);
                    }}
                    aria-label={`${value} star${value === 1 ? "" : "s"}`}
                  >
                    <Star size={25} fill={value <= rating ? "currentColor" : "none"} />
                  </button>
                ))}
              </div>
              <textarea
                value={body}
                onChange={(event) => setBody(event.target.value)}
                maxLength={1000}
                rows={3}
                aria-label="Your review"
                disabled={!reviewReady}
              />
            </div>

            {error && <p className="form-message">{error}</p>}
            <div className="dialog-actions">
              <button
                className="primary-button"
                type="button"
                onClick={() => void complete()}
                disabled={saving || !reviewReady}
              >
                <Check size={18} />
                {!reviewReady ? "Loading…" : saving ? "Saving…" : "Mark completed"}
              </button>
            </div>
          </>
        )}
      </section>
    </div>
  );
}
