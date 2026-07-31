import type { WalkingRoute } from "../types";

export function formatWalkingRouteSummary(route: WalkingRoute): string {
  return `${formatDistance(route.distance_meters)} · ${formatDuration(route.duration_seconds)} walking`;
}

export function formatDistance(meters: number): string {
  if (meters < 1_000) return `${Math.round(meters)} m`;
  return `${(meters / 1_000).toFixed(1)} km`;
}

export function formatDuration(seconds: number): string {
  if (seconds <= 0) return "0 min";
  const minutes = Math.max(1, Math.round(seconds / 60));
  if (minutes < 60) return `${minutes} min`;
  const hours = Math.floor(minutes / 60);
  const remainder = minutes % 60;
  return remainder ? `${hours} hr ${remainder} min` : `${hours} hr`;
}
