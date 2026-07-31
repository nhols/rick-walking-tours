import { useEffect, useRef } from "react";
import maplibregl, {
  type GeoJSONSource,
  type Map as MapLibreMap,
  type MapMouseEvent
} from "maplibre-gl";
import { ChevronRight, List, MapPin, Star, X } from "lucide-react";
import { useOnlineStatus } from "../lib/online";
import type { Tour } from "../types";

interface LibraryMapProps {
  tours: Tour[];
  viewerId: string;
  clusterTours: Tour[] | null;
  onSelect: (tourId: string) => void;
  onClusterChange: (tours: Tour[] | null) => void;
  onShowList: () => void;
}

export function LibraryMap({
  tours,
  viewerId,
  clusterTours,
  onSelect,
  onClusterChange,
  onShowList
}: LibraryMapProps) {
  const online = useOnlineStatus();
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MapLibreMap | null>(null);
  const onSelectRef = useRef(onSelect);
  const onClusterChangeRef = useRef(onClusterChange);
  onSelectRef.current = onSelect;
  onClusterChangeRef.current = onClusterChange;

  const mappedTours = tours.filter(
    (tour) => tour.start_lat !== null && tour.start_lon !== null
  );
  const tourSignature = JSON.stringify(
    mappedTours.map((tour) => [tour.id, tour.start_lat, tour.start_lon])
  );

  useEffect(() => {
    onClusterChangeRef.current(null);
  }, [tourSignature]);

  useEffect(() => {
    if (!containerRef.current || !online || mappedTours.length === 0) return;

    const toursById = new Map(mappedTours.map((tour) => [tour.id, tour]));
    const map = new maplibregl.Map({
      container: containerRef.current,
      style: "https://tiles.openfreemap.org/styles/bright",
      center: [mappedTours[0].start_lon!, mappedTours[0].start_lat!],
      zoom: 12,
      attributionControl: false
    });
    mapRef.current = map;
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");
    map.addControl(new maplibregl.AttributionControl({ compact: true }));

    const data = {
      type: "FeatureCollection" as const,
      features: mappedTours.map((tour) => ({
        type: "Feature" as const,
        properties: { tourId: tour.id },
        geometry: {
          type: "Point" as const,
          coordinates: [tour.start_lon!, tour.start_lat!]
        }
      }))
    };

    const closeCluster = () => {
      onClusterChangeRef.current(null);
    };

    const handleClusterClick = async (event: MapMouseEvent) => {
      const feature = map.queryRenderedFeatures(event.point, {
        layers: ["library-clusters"]
      })[0];
      const clusterId = Number(feature?.properties?.cluster_id);
      const pointCount = Number(feature?.properties?.point_count);
      const source = map.getSource("library-tours") as GeoJSONSource | undefined;
      if (!source || !Number.isFinite(clusterId) || !Number.isFinite(pointCount)) return;

      const leaves = await source.getClusterLeaves(clusterId, pointCount, 0);
      const nextTours = leaves
        .map((leaf) => toursById.get(String(leaf.properties?.tourId)))
        .filter((tour): tour is Tour => Boolean(tour));
      onClusterChangeRef.current(nextTours);
    };

    const handleTourClick = (event: MapMouseEvent) => {
      const feature = map.queryRenderedFeatures(event.point, {
        layers: ["library-tour-points"]
      })[0];
      const tourId = feature?.properties?.tourId;
      if (tourId) onSelectRef.current(String(tourId));
    };

    const handleMapClick = (event: MapMouseEvent) => {
      const features = map.queryRenderedFeatures(event.point, {
        layers: ["library-clusters", "library-tour-points"]
      });
      if (features.length === 0) closeCluster();
    };

    const showPointer = () => {
      map.getCanvas().style.cursor = "pointer";
    };
    const hidePointer = () => {
      map.getCanvas().style.cursor = "";
    };

    map.on("load", () => {
      map.addSource("library-tours", {
        type: "geojson",
        data,
        cluster: true,
        clusterMaxZoom: 14,
        clusterRadius: 52
      });
      map.addLayer({
        id: "library-clusters",
        type: "circle",
        source: "library-tours",
        filter: ["has", "point_count"],
        paint: {
          "circle-color": "#e6323b",
          "circle-radius": ["step", ["get", "point_count"], 20, 10, 25, 30, 31],
          "circle-stroke-color": "#ffffff",
          "circle-stroke-width": 3
        }
      });
      map.addLayer({
        id: "library-cluster-count",
        type: "symbol",
        source: "library-tours",
        filter: ["has", "point_count"],
        layout: {
          "text-field": ["get", "point_count_abbreviated"],
          "text-size": 12
        },
        paint: { "text-color": "#ffffff" }
      });
      map.addLayer({
        id: "library-tour-points",
        type: "circle",
        source: "library-tours",
        filter: ["!", ["has", "point_count"]],
        paint: {
          "circle-color": "#e6323b",
          "circle-radius": 9,
          "circle-stroke-color": "#ffffff",
          "circle-stroke-width": 3
        }
      });

      if (mappedTours.length > 1) {
        const bounds = new maplibregl.LngLatBounds();
        mappedTours.forEach((tour) => bounds.extend([tour.start_lon!, tour.start_lat!]));
        map.fitBounds(bounds, { padding: 60, maxZoom: 13 });
      }
    });

    map.on("click", "library-clusters", handleClusterClick);
    map.on("click", "library-tour-points", handleTourClick);
    map.on("click", handleMapClick);
    map.on("mouseenter", "library-clusters", showPointer);
    map.on("mouseenter", "library-tour-points", showPointer);
    map.on("mouseleave", "library-clusters", hidePointer);
    map.on("mouseleave", "library-tour-points", hidePointer);

    return () => {
      map.remove();
      mapRef.current = null;
    };
  }, [online, tourSignature]);

  const closeCluster = () => {
    onClusterChange(null);
  };

  return (
    <div className="library-map-shell">
      <button className="library-map-list-button" type="button" onClick={onShowList}>
        <List size={17} /> List
      </button>
      {!online ? (
        <div className="library-map-empty">
          <MapPin size={26} />
          <p>Map unavailable offline</p>
        </div>
      ) : mappedTours.length === 0 ? (
        <div className="library-map-empty">
          <MapPin size={26} />
          <p>No mapped tours in this view.</p>
        </div>
      ) : (
        <div className="library-map" ref={containerRef} />
      )}

      {clusterTours && clusterTours.length > 0 && (
        <section className="cluster-sheet" aria-label="Tours in this cluster">
          <header>
            <strong>{clusterTours.length} tours here</strong>
            <button type="button" onClick={closeCluster} aria-label="Close cluster list">
              <X size={18} />
            </button>
          </header>
          <div className="cluster-sheet-list">
            {clusterTours.map((tour) => (
              <button type="button" key={tour.id} onClick={() => onSelect(tour.id)}>
                <span>
                  <strong>{tour.title ?? tour.input.location}</strong>
                  <small>
                    {tour.owner_id === viewerId ? "Yours" : "Community"}
                    {tour.review_count ? (
                      <><Star size={11} fill="currentColor" />{tour.average_rating?.toFixed(1)}</>
                    ) : null}
                  </small>
                </span>
                <ChevronRight size={17} />
              </button>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
