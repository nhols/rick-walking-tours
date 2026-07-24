import { useEffect, useRef } from "react";
import maplibregl, { type Map as MapLibreMap } from "maplibre-gl";
import type { Checkpoint } from "../types";

interface CheckpointMapProps {
  checkpoints: Checkpoint[];
  selectedId?: string;
  onSelect: (checkpointId: string) => void;
}

export function CheckpointMap({
  checkpoints,
  selectedId,
  onSelect
}: CheckpointMapProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MapLibreMap | null>(null);
  const onSelectRef = useRef(onSelect);
  onSelectRef.current = onSelect;
  const checkpointSignature = JSON.stringify(
    checkpoints.map(({ id, lat, lon, position, title }) => ({
      id,
      lat,
      lon,
      position,
      title
    }))
  );
  const selectedCheckpoint = checkpoints.find(
    (checkpoint) => checkpoint.id === selectedId
  );
  const selectedLatitude = selectedCheckpoint?.lat;
  const selectedLongitude = selectedCheckpoint?.lon;

  useEffect(() => {
    if (!containerRef.current || checkpoints.length === 0 || !navigator.onLine) {
      return;
    }

    const map = new maplibregl.Map({
      container: containerRef.current,
      style: "https://tiles.openfreemap.org/styles/liberty",
      center: [checkpoints[0].lon, checkpoints[0].lat],
      zoom: 14,
      attributionControl: false
    });
    mapRef.current = map;
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");
    map.addControl(
      new maplibregl.GeolocateControl({
        positionOptions: { enableHighAccuracy: true },
        trackUserLocation: true,
        showAccuracyCircle: true
      }),
      "top-right"
    );
    map.addControl(new maplibregl.AttributionControl({ compact: true }));

    const bounds = new maplibregl.LngLatBounds();
    const markers = checkpoints.map((checkpoint) => {
      bounds.extend([checkpoint.lon, checkpoint.lat]);
      const element = document.createElement("button");
      element.type = "button";
      element.className = "map-marker";
      element.setAttribute("aria-label", `Open ${checkpoint.title}`);
      element.dataset.checkpointId = checkpoint.id;
      const badge = document.createElement("span");
      badge.className = "map-marker-badge";
      badge.textContent = String(checkpoint.position);
      element.append(badge);
      element.addEventListener("click", () => onSelectRef.current(checkpoint.id));
      return new maplibregl.Marker({ element })
        .setLngLat([checkpoint.lon, checkpoint.lat])
        .addTo(map);
    });

    map.on("load", () => {
      map.addSource("route", {
        type: "geojson",
        data: {
          type: "Feature",
          properties: {},
          geometry: {
            type: "LineString",
            coordinates: checkpoints.map((checkpoint) => [
              checkpoint.lon,
              checkpoint.lat
            ])
          }
        }
      });
      map.addLayer({
        id: "route",
        type: "line",
        source: "route",
        paint: {
          "line-color": "#d9573f",
          "line-width": 4,
          "line-opacity": 0.8
        }
      });
      if (checkpoints.length > 1) {
        map.fitBounds(bounds, { padding: 56, maxZoom: 15 });
      }
    });

    return () => {
      markers.forEach((marker) => marker.remove());
      map.remove();
      mapRef.current = null;
    };
  }, [checkpointSignature]);

  useEffect(() => {
    if (!mapRef.current) return;
    const elements = mapRef.current.getContainer().querySelectorAll(".map-marker");
    elements.forEach((element) => {
      element.classList.toggle(
        "is-selected",
        (element as HTMLElement).dataset.checkpointId === selectedId
      );
    });
    if (selectedLatitude !== undefined && selectedLongitude !== undefined) {
      mapRef.current.easeTo({
        center: [selectedLongitude, selectedLatitude],
        duration: 450
      });
    }
  }, [selectedId, selectedLatitude, selectedLongitude]);

  if (!navigator.onLine) {
    return (
      <div className="map-offline">
        <span>Map unavailable offline</span>
        <small>Your checkpoints and audio are still available.</small>
      </div>
    );
  }

  return <div className="checkpoint-map" ref={containerRef} />;
}
