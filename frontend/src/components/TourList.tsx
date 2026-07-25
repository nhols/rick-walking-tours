import {
  Check,
  ChevronRight,
  Download,
  LoaderCircle,
  MapPin,
  Trash2
} from "lucide-react";
import { STATUS_LABELS, type Tour } from "../types";


interface TourListProps {
  tours: Tour[];
  loading: boolean;
  online: boolean;
  selectedId: string | null;
  downloadedIds: Set<string>;
  downloadingIds: Set<string>;
  onSelect: (id: string) => void;
  onDownload: (id: string) => void;
  onRemoveDownload: (id: string) => void;
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
        <small>{props.online ? "Create one to begin." : "No downloaded tours."}</small>
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
  downloadedIds,
  downloadingIds,
  onSelect,
  onDownload,
  onRemoveDownload
}: TourListProps & { title: string }) {
  if (tours.length === 0) return null;
  return (
    <section className="tour-section">
      <p className="section-label">{title}</p>
      {tours.map((tour) => {
        const isDownloaded = downloadedIds.has(tour.id);
        const isDownloading = downloadingIds.has(tour.id);
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
            {tour.status === "ready" && (
              <button
                className={`tour-download-button ${isDownloaded ? "is-downloaded" : ""}`}
                type="button"
                aria-label={
                  isDownloaded
                    ? `${tourName} downloaded`
                    : isDownloading
                      ? `Downloading ${tourName}`
                      : `Download ${tourName} for offline listening`
                }
                title={
                  isDownloaded
                    ? "Remove offline download"
                    : isDownloading
                      ? "Downloading…"
                      : "Download for offline listening"
                }
                disabled={isDownloading}
                onClick={() =>
                  isDownloaded ? onRemoveDownload(tour.id) : onDownload(tour.id)
                }
              >
                {isDownloading ? (
                  <LoaderCircle className="spin" size={18} />
                ) : isDownloaded ? (
                  <span className="downloaded-state-icons">
                    <Check size={18} />
                    <Trash2 className="remove-download" size={17} />
                  </span>
                ) : (
                  <Download size={18} />
                )}
              </button>
            )}
          </div>
        );
      })}
    </section>
  );
}
