import { lazy, useState } from "react";
import { ChevronUp, MapPin } from "lucide-react";
import type { TourBundle } from "../types";
import { ChapterAudio } from "./ChapterAudio";


const CheckpointMap = lazy(() => import("./CheckpointMap"));

export function ReadyTour({ bundle }: { bundle: TourBundle }) {
  const approvedPlan =
    bundle.plans.find((plan) => plan.id === bundle.tour.approved_plan_id) ??
    bundle.plans.at(-1);
  const checkpoints = approvedPlan?.payload.checkpoints ?? [];
  const [selectedId, setSelectedId] = useState(checkpoints[0]?.id);
  const [detailsOpen, setDetailsOpen] = useState(false);
  const selected = checkpoints.find((item) => item.id === selectedId) ?? checkpoints[0];
  const chapter = bundle.chapters.find((item) => item.checkpoint_id === selected?.id);

  return (
    <div className="ready-tour">
      <div className="ready-map">
        <CheckpointMap
          checkpoints={checkpoints}
          selectedId={selected?.id}
          onSelect={setSelectedId}
        />
      </div>
      {selected && (
        <div className={`player-shell ${detailsOpen ? "is-expanded" : ""}`}>
          <aside
            className="checkpoint-details-overlay"
            aria-label="Checkpoint details"
            aria-hidden={!detailsOpen}
          >
            <article className="chapter-card">
              <div className="chapter-number">Stop {selected.position}</div>
              <h2>{chapter?.title ?? selected.title}</h2>
              <a
                className="address"
                href={`https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(`${selected.lat},${selected.lon}`)}`}
                target="_blank"
                rel="noreferrer"
                tabIndex={detailsOpen ? 0 : -1}
              >
                <MapPin size={16} />
                {selected.formatted_address ?? "Open in Maps"}
              </a>
              <p className="transcript">{chapter?.narration ?? selected.description}</p>
            </article>
          </aside>
          <section className="player-dock">
            <button
              className="player-details-trigger"
              type="button"
              onClick={() => setDetailsOpen((open) => !open)}
              aria-expanded={detailsOpen}
              aria-label={`${detailsOpen ? "Collapse" : "Open"} details for ${chapter?.title ?? selected.title}`}
            >
              <span>
                <small>Stop {selected.position} of {checkpoints.length}</small>
                <strong>{chapter?.title ?? selected.title}</strong>
              </span>
              <ChevronUp
                className={`details-chevron ${detailsOpen ? "is-open" : ""}`}
                size={21}
              />
            </button>
            <div className="player-audio">
              {chapter ? <ChapterAudio chapter={chapter} /> : <span>Audio unavailable</span>}
            </div>
          </section>
        </div>
      )}
    </div>
  );
}
