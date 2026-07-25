import { Suspense, useCallback, useEffect, useState } from "react";
import { ArrowLeft, CircleAlert, LoaderCircle, RefreshCw } from "lucide-react";
import { useOnlineStatus } from "../lib/online";
import { loadTourBundle } from "../lib/supabase";
import { ACTIVE_STATUSES, type TourBundle } from "../types";
import { GenerationReview } from "./GenerationReview";
import { ReadyTour } from "./ReadyTour";

interface TourDetailProps {
  tourId: string;
  downloadedBundle?: TourBundle;
  onBack: () => void;
  onChanged: () => Promise<void>;
}

export function TourDetail({
  tourId,
  downloadedBundle,
  onBack,
  onChanged
}: TourDetailProps) {
  const online = useOnlineStatus();
  const [bundle, setBundle] = useState<TourBundle | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    if (!online) {
      setBundle(downloadedBundle ?? null);
      setError(downloadedBundle ? null : "This tour has not been downloaded.");
      setLoading(false);
      return;
    }
    try {
      setBundle(await loadTourBundle(tourId));
      setError(null);
    } catch (loadError) {
      setBundle(downloadedBundle ?? null);
      setError(
        loadError instanceof Error ? loadError.message : "Could not load this tour"
      );
    } finally {
      setLoading(false);
    }
  }, [downloadedBundle, online, tourId]);

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
          {error && <div className="detail-warning"><CircleAlert size={17} />{error}</div>}
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
