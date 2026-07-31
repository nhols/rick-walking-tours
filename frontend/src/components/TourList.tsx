import {
  Check,
  ChevronRight,
  LoaderCircle,
  MapPin,
  Square,
  Star
} from "lucide-react";
import { STATUS_LABELS, type Tour } from "../types";


interface TourListProps {
  tours: Tour[];
  loading: boolean;
  online: boolean;
  selectedId: string | null;
  onSelect: (id: string) => void;
  onComplete: (tour: Tour) => void;
  publicMode?: boolean;
}

export function TourList(props: TourListProps) {
  if (props.loading && props.tours.length === 0) {
    return (
      <div className="list-loader">
        <LoaderCircle className="spin" />Loading tours…
      </div>
    );
  }
  if (props.tours.length === 0) {
    return (
      <div className="empty-list">
        <MapPin size={24} />
        <p>{props.publicMode ? "No public tours yet." : "No tours yet."}</p>
        <small>
          {props.online
            ? props.publicMode ? "Published tours will appear here." : "Create one to begin."
            : "Tours require an internet connection."}
        </small>
      </div>
    );
  }
  if (props.publicMode) {
    return <TourSection {...props} title="Shared by the community" tours={props.tours} />;
  }
  return (
    <>
      <TourSection
        {...props}
        title="In progress"
        tours={props.tours.filter((tour) => tour.status !== "ready")}
      />
      <TourSection
        {...props}
        title="Ready to walk"
        tours={props.tours.filter((tour) => tour.status === "ready")}
      />
    </>
  );
}

function TourSection({
  title,
  tours,
  selectedId,
  onSelect,
  onComplete,
  publicMode
}: TourListProps & { title: string }) {
  if (tours.length === 0) return null;
  return (
    <section className="tour-section">
      <p className="section-label">{title}</p>
      {tours.map((tour) => {
        const tourName = tour.title ?? tour.input.location;
        return (
          <div
            className={`tour-row ${selectedId === tour.id ? "selected" : ""}`}
            key={tour.id}
          >
            {tour.status === "ready" && (
              <button
                className={`tour-completion-checkbox ${tour.completed_at ? "completed" : ""}`}
                type="button"
                role="checkbox"
                aria-checked={Boolean(tour.completed_at)}
                aria-label={
                  tour.completed_at
                    ? `Remove completed status from ${tourName}`
                    : `Mark ${tourName} completed`
                }
                title={
                  tour.completed_at
                    ? `Completed ${new Date(tour.completed_at).toLocaleDateString()}`
                    : "Mark completed"
                }
                onClick={() => onComplete(tour)}
              >
                {tour.completed_at ? <Check size={18} /> : <Square size={20} />}
              </button>
            )}
            <button className="tour-row-main" onClick={() => onSelect(tour.id)}>
              {tour.status !== "ready" && (
                <span className="tour-row-icon"><MapPin size={18} /></span>
              )}
              <span className="tour-row-copy">
                <strong>{tourName}</strong>
                {publicMode ? (
                  <small className="tour-rating">
                    <Star size={12} fill="currentColor" />
                    {tour.review_count
                      ? `${tour.average_rating?.toFixed(1)} (${tour.review_count})`
                      : "Not rated yet"}
                  </small>
                ) : (
                  <small>{STATUS_LABELS[tour.status]}</small>
                )}
              </span>
              <ChevronRight size={17} />
            </button>
          </div>
        );
      })}
    </section>
  );
}
