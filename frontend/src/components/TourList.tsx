import {
  ChevronRight,
  LoaderCircle,
  MapPin
} from "lucide-react";
import { STATUS_LABELS, type Tour } from "../types";


interface TourListProps {
  tours: Tour[];
  loading: boolean;
  online: boolean;
  selectedId: string | null;
  onSelect: (id: string) => void;
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
        <MapPin size={24} /><p>No tours yet.</p>
        <small>{props.online ? "Create one to begin." : "Tours require an internet connection."}</small>
      </div>
    );
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
  onSelect
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
            <button className="tour-row-main" onClick={() => onSelect(tour.id)}>
              <span className="tour-row-icon"><MapPin size={18} /></span>
              <span className="tour-row-copy">
                <strong>{tourName}</strong>
                <small>{STATUS_LABELS[tour.status]}</small>
              </span>
              <ChevronRight size={17} />
            </button>
          </div>
        );
      })}
    </section>
  );
}
