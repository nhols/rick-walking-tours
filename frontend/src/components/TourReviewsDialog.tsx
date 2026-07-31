import { useState, type FormEvent } from "react";
import { Star, Trash2, X } from "lucide-react";
import { deleteTourReview, saveTourReview } from "../lib/reviews";
import type { TourBundle } from "../types";

interface TourReviewsDialogProps {
  bundle: TourBundle;
  viewerId: string;
  onClose: () => void;
  onChanged: () => Promise<void>;
}

export function TourReviewsDialog({
  bundle,
  viewerId,
  onClose,
  onChanged
}: TourReviewsDialogProps) {
  const currentReview = bundle.reviews.find((review) => review.user_id === viewerId);
  const [rating, setRating] = useState(currentReview?.rating ?? 0);
  const [body, setBody] = useState(currentReview?.body ?? "");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const average = bundle.reviews.length
    ? bundle.reviews.reduce((sum, review) => sum + review.rating, 0) /
      bundle.reviews.length
    : null;

  async function save(event: FormEvent) {
    event.preventDefault();
    if (!rating || !body.trim()) {
      setError("Choose a rating and write a short review.");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      await saveTourReview(
        bundle.tour.id,
        viewerId,
        rating,
        body.trim()
      );
      await onChanged();
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : "Could not save review");
    } finally {
      setSaving(false);
    }
  }

  async function removeReview() {
    if (!currentReview) return;
    setSaving(true);
    setError(null);
    try {
      await deleteTourReview(currentReview.id);
      setRating(0);
      setBody("");
      await onChanged();
    } catch (deleteError) {
      setError(
        deleteError instanceof Error ? deleteError.message : "Could not delete review"
      );
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="dialog-backdrop review-dialog-backdrop" role="presentation">
      <section
        className="dialog reviews-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="reviews-title"
      >
        <header className="reviews-header">
          <div>
            <p className="eyebrow">Tour feedback</p>
            <h2 id="reviews-title">Ratings &amp; reviews</h2>
          </div>
          <button
            className="icon-button"
            onClick={onClose}
            aria-label="Close reviews"
            title="Close"
          >
            <X size={20} />
          </button>
        </header>

        <div className="rating-overview">
          <Star size={24} fill="currentColor" />
          <strong>{average?.toFixed(1) ?? "—"}</strong>
          <span>
            {bundle.reviews.length} {bundle.reviews.length === 1 ? "review" : "reviews"}
          </span>
        </div>

        <form className="review-form" onSubmit={(event) => void save(event)}>
          <div className="star-picker" aria-label="Star rating">
            {[1, 2, 3, 4, 5].map((value) => (
              <button
                type="button"
                key={value}
                className={value <= rating ? "selected" : ""}
                onClick={() => setRating(value)}
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
            placeholder="How was the tour?"
            aria-label="Your review"
          />
          {error && <p className="form-message">{error}</p>}
          <div className="review-form-actions">
            {currentReview && (
              <button
                type="button"
                className="icon-button danger-button"
                onClick={() => void removeReview()}
                disabled={saving}
                aria-label="Delete your review"
                title="Delete your review"
              >
                <Trash2 size={18} />
              </button>
            )}
            <button className="primary-button" type="submit" disabled={saving}>
              {saving ? "Saving…" : currentReview ? "Update review" : "Post review"}
            </button>
          </div>
        </form>

        <div className="reviews-list">
          {bundle.reviews.length === 0 ? (
            <p className="reviews-empty">No reviews yet.</p>
          ) : (
            bundle.reviews.map((review) => (
              <article className="review-card" key={review.id}>
                <div className="review-card-heading">
                  <span
                    className="review-card-stars"
                    aria-label={`${review.rating} out of 5 stars`}
                  >
                    {[1, 2, 3, 4, 5].map((value) => (
                      <Star
                        key={value}
                        size={13}
                        fill={value <= review.rating ? "currentColor" : "none"}
                      />
                    ))}
                  </span>
                  <small>{review.user_id === viewerId ? "You" : "Rick walker"}</small>
                </div>
                <p>{review.body}</p>
              </article>
            ))
          )}
        </div>
      </section>
    </div>
  );
}
