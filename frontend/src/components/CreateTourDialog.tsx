import { useState, type FormEvent } from "react";
import { LoaderCircle, Sparkles } from "lucide-react";
import { createTour } from "../lib/api";


export function CreateTourDialog({
  onClose,
  onCreated
}: {
  onClose: () => void;
  onCreated: (tourId: string) => void;
}) {
  const [location, setLocation] = useState("");
  const [request, setRequest] = useState("");
  const [minStops, setMinStops] = useState(2);
  const [maxStops, setMaxStops] = useState(10);
  const [maxDistanceKm, setMaxDistanceKm] = useState(10);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const command = await createTour({
        location,
        request,
        min_stops: minStops,
        max_stops: maxStops,
        max_checkpoint_distance_km: maxDistanceKm
      });
      onCreated(command.tour_id);
    } catch (submitError) {
      setError(
        submitError instanceof Error ? submitError.message : "Could not create tour"
      );
      setBusy(false);
    }
  }

  return (
    <div
      className="dialog-backdrop"
      role="presentation"
      onMouseDown={(event) =>
        event.target === event.currentTarget && !busy && onClose()
      }
    >
      <form className="dialog" onSubmit={submit}>
        <h2>Create a tour</h2>
        <label>
          Place
          <input
            placeholder="e.g. Edinburgh Old Town"
            value={location}
            onChange={(event) => setLocation(event.target.value)}
            required
          />
        </label>
        <label>
          What are you interested in?
          <textarea
            placeholder="e.g. Roman history and architecture, about 45 minutes"
            value={request}
            onChange={(event) => setRequest(event.target.value)}
            required
            rows={5}
          />
        </label>
        <div className="form-grid">
          <label>
            Minimum stops
            <input
              type="number"
              min={1}
              max={20}
              value={minStops}
              onChange={(event) => setMinStops(event.currentTarget.valueAsNumber)}
              required
            />
          </label>
          <label>
            Maximum stops
            <input
              type="number"
              min={minStops}
              max={20}
              value={maxStops}
              onChange={(event) => setMaxStops(event.currentTarget.valueAsNumber)}
              required
            />
          </label>
        </div>
        <label>
          Maximum distance between any two stops (km)
          <input
            type="number"
            min={0.1}
            max={100}
            step="any"
            value={maxDistanceKm}
            onChange={(event) => setMaxDistanceKm(event.currentTarget.valueAsNumber)}
            required
          />
        </label>
        {error && <p className="form-message">{error}</p>}
        {busy && (
          <p className="working-note">
            <LoaderCircle className="spin" size={17} />
            Generating your route…
          </p>
        )}
        <div className="dialog-actions">
          <button
            className="secondary-button"
            type="button"
            onClick={onClose}
            disabled={busy}
          >
            Cancel
          </button>
          <button className="primary-button" disabled={busy}>
            <Sparkles size={17} />Start planning
          </button>
        </div>
      </form>
    </div>
  );
}
