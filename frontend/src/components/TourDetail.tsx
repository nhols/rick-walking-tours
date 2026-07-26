import { Suspense, useCallback, useEffect, useRef, useState } from "react";
import PublicIcon from "@mui/icons-material/Public";
import PublicOffIcon from "@mui/icons-material/PublicOff";
import {
  ArrowLeft,
  CircleAlert,
  LoaderCircle,
  RefreshCw,
  Share2,
  Star
} from "lucide-react";
import { useOnlineStatus } from "../lib/online";
import { loadTourBundle, setTourPublic } from "../lib/tours";
import { ACTIVE_STATUSES, type TourBundle } from "../types";
import { GenerationReview } from "./GenerationReview";
import { ReadyTour } from "./ReadyTour";
import { TourReviewsDialog } from "./TourReviewsDialog";

interface TourDetailProps {
  tourId: string;
  viewerId: string;
  onBack: () => void;
  onChanged: () => Promise<void>;
}

export function TourDetail({
  tourId,
  viewerId,
  onBack,
  onChanged
}: TourDetailProps) {
  const online = useOnlineStatus();
  const [bundle, setBundle] = useState<TourBundle | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [visibilitySaving, setVisibilitySaving] = useState(false);
  const [showPublishConfirm, setShowPublishConfirm] = useState(false);
  const [showReviews, setShowReviews] = useState(false);
  const refreshSequence = useRef(0);

  const refresh = useCallback(async () => {
    const sequence = ++refreshSequence.current;
    if (!online) {
      setBundle(null);
      setError("Tours require an internet connection.");
      setLoading(false);
      return;
    }
    try {
      const nextBundle = await loadTourBundle(tourId);
      if (sequence !== refreshSequence.current) return;
      setBundle(nextBundle);
      setError(null);
    } catch (loadError) {
      if (sequence !== refreshSequence.current) return;
      setBundle(null);
      setError(
        loadError instanceof Error ? loadError.message : "Could not load this tour"
      );
    } finally {
      if (sequence === refreshSequence.current) setLoading(false);
    }
  }, [online, tourId]);

  useEffect(() => {
    setLoading(true);
    void refresh();
  }, [refresh]);

  useEffect(() => {
    if (!online || !bundle || !ACTIVE_STATUSES.includes(bundle.tour.status)) return;
    const timer = window.setInterval(() => void refresh(), 3000);
    return () => window.clearInterval(timer);
  }, [bundle, online, refresh]);

  useEffect(() => {
    if (!online) return;
    const handleFocus = () => void refresh();
    window.addEventListener("focus", handleFocus);
    return () => window.removeEventListener("focus", handleFocus);
  }, [online, refresh]);

  const tour = bundle?.tour;
  const isReady = tour?.status === "ready";
  const isOwner = tour?.owner_id === viewerId;
  const averageRating = bundle?.reviews.length
    ? bundle.reviews.reduce((sum, review) => sum + review.rating, 0) /
      bundle.reviews.length
    : null;

  async function setVisibility(isPublic: boolean) {
    if (!tour) return;
    setVisibilitySaving(true);
    setActionError(null);
    try {
      await setTourPublic(tour.id, isPublic);
      await Promise.all([onChanged(), refresh()]);
    } catch (visibilityError) {
      setActionError(
        visibilityError instanceof Error
          ? visibilityError.message
          : "Could not change tour visibility"
      );
    } finally {
      setVisibilitySaving(false);
    }
  }

  async function shareTour() {
    if (!tour) return;
    const shareData = {
      title: tour.title ?? tour.input.location,
      url: window.location.href
    };
    try {
      if (navigator.share) {
        await navigator.share(shareData);
      } else {
        await navigator.clipboard.writeText(shareData.url);
      }
    } catch (shareError) {
      if (shareError instanceof DOMException && shareError.name === "AbortError") return;
      setActionError("Could not share this tour.");
    }
  }

  return (
    <div className={`detail-page ${isReady ? "is-ready" : ""}`}>
      <header className="detail-header">
        <button
          className="back-button"
          aria-label="Back to library"
          title="Back to library"
          onClick={onBack}
        >
          <ArrowLeft size={21} />
        </button>
        <div className="detail-title">
          <p className="eyebrow">{tour?.input?.location ?? "Walking tour"}</p>
          <h1>
            {tour?.title ??
              tour?.input?.location ??
              (loading ? "Loading tour" : "Tour unavailable")}
          </h1>
        </div>
        {tour && isReady && (
          <div className="detail-actions">
            {isOwner && (
              <button
                className={`icon-button ${tour.is_public ? "active" : ""}`}
                onClick={() => {
                  if (tour.is_public) {
                    void setVisibility(false);
                  } else {
                    setShowPublishConfirm(true);
                  }
                }}
                disabled={visibilitySaving}
                aria-label={tour.is_public ? "Make tour private" : "Publish tour"}
                title={tour.is_public ? "Make private" : "Publish"}
              >
                {tour.is_public ? (
                  <PublicIcon fontSize="small" />
                ) : (
                  <PublicOffIcon fontSize="small" />
                )}
              </button>
            )}
            <button
              className="icon-button rating-button"
              onClick={() => setShowReviews(true)}
              aria-label="Open ratings and reviews"
              title="Ratings and reviews"
            >
              <Star size={18} fill={averageRating ? "currentColor" : "none"} />
              {averageRating && <span>{averageRating.toFixed(1)}</span>}
            </button>
            {tour.is_public && (
              <button
                className="icon-button"
                onClick={() => void shareTour()}
                aria-label="Share tour"
                title="Share"
              >
                <Share2 size={18} />
              </button>
            )}
          </div>
        )}
      </header>

      {loading && !bundle ? (
        <PageLoader />
      ) : !bundle ? (
        <div className="detail-error">
          <CircleAlert size={26} />
          <h2>Tour unavailable</h2>
          <p>{error}</p>
          {online && (
            <button className="secondary-button" onClick={() => void refresh()}>
              <RefreshCw size={17} /> Try again
            </button>
          )}
        </div>
      ) : (
        <>
          {(error || actionError) && (
            <div className="detail-warning">
              <CircleAlert size={17} />{actionError ?? error}
            </div>
          )}
          <Suspense fallback={<PageLoader />}>
            {isReady ? (
              <ReadyTour bundle={bundle} />
            ) : (
              <GenerationReview
                bundle={bundle}
                onChanged={async () => {
                  await Promise.all([onChanged(), refresh()]);
                }}
              />
            )}
          </Suspense>
        </>
      )}
      {bundle && showReviews && (
        <TourReviewsDialog
          bundle={bundle}
          viewerId={viewerId}
          onClose={() => setShowReviews(false)}
          onChanged={async () => {
            await Promise.all([onChanged(), refresh()]);
          }}
        />
      )}
      {tour && showPublishConfirm && (
        <div className="dialog-backdrop" role="presentation">
          <section
            className="dialog confirmation-dialog"
            role="dialog"
            aria-modal="true"
            aria-labelledby="publish-title"
          >
            <span className="confirmation-icon"><PublicIcon /></span>
            <h2 id="publish-title">Make this tour public?</h2>
            <p>
              All users will be able to find, open, share,
              rate, and review this tour. You can make it private again at any time.
            </p>
            <div className="dialog-actions">
              <button
                className="secondary-button"
                onClick={() => setShowPublishConfirm(false)}
                disabled={visibilitySaving}
              >
                Cancel
              </button>
              <button
                className="primary-button"
                onClick={() => {
                  setShowPublishConfirm(false);
                  void setVisibility(true);
                }}
                disabled={visibilitySaving}
              >
                Make public
              </button>
            </div>
          </section>
        </div>
      )}
    </div>
  );
}

function PageLoader() {
  return (
    <div className="full-loader">
      <LoaderCircle className="spin" size={26} />Loading tour…
    </div>
  );
}
