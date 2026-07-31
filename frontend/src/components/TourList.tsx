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
  viewerId: string;
  variant: "build" | "library";
  onSelect: (id: string) => void;
  onComplete: (tour: Tour) => void;
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
        <p>{props.variant === "build" ? "Nothing in build." : "No tours found."}</p>
        <small>
          {props.online
            ? props.variant === "build"
              ? "Create a tour to get started."
              : "Try another library filter."
            : "Tours require an internet connection."}
        </small>
      </div>
    );
  }

  return (
    <div className="tour-rows">
      {props.tours.map((tour) => {
        const tourName = tour.title ?? tour.input.location;
        const isOwner = tour.owner_id === props.viewerId;
        return (
          <div
            className={`tour-row ${props.selectedId === tour.id ? "selected" : ""}`}
            key={tour.id}
          >
            {props.variant === "library" && (
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
                onClick={() => props.onComplete(tour)}
              >
                {tour.completed_at ? <Check size={18} /> : <Square size={20} />}
              </button>
            )}
            <button className="tour-row-main" onClick={() => props.onSelect(tour.id)}>
              {props.variant === "build" && (
                <span className="tour-row-icon"><MapPin size={18} /></span>
              )}
              <span className="tour-row-copy">
                <strong>{tourName}</strong>
                {props.variant === "build" ? (
                  <small>{STATUS_LABELS[tour.status]}</small>
                ) : (
                  <small className="tour-library-meta">
                    <span>{isOwner ? "Yours" : "Community"}</span>
                    <span className="tour-rating">
                      <Star size={12} fill={tour.review_count ? "currentColor" : "none"} />
                      {tour.review_count
                        ? `${tour.average_rating?.toFixed(1)} (${tour.review_count})`
                        : "Not rated"}
                    </span>
                  </small>
                )}
              </span>
              <ChevronRight size={17} />
            </button>
          </div>
        );
      })}
    </div>
  );
}
