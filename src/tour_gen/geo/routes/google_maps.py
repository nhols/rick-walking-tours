import os
from collections.abc import Mapping
from typing import Any, TypeAlias

import httpx

from tour_gen.geo.models import GeoJsonLineString, GeoPosition
from tour_gen.geo.routes import RouteLeg, WalkingRoute


JsonObject: TypeAlias = Mapping[str, Any]


class GoogleMapsRouter:
    endpoint = "https://routes.googleapis.com/directions/v2:computeRoutes"

    def __init__(self, api_key: str | None = None) -> None:
        resolved_api_key = api_key or os.environ.get("GOOGLE_MAPS_API_KEY")
        if not resolved_api_key:
            raise RuntimeError("GOOGLE_MAPS_API_KEY must be set in .env")
        self.api_key: str = resolved_api_key

    async def walking_route(self, waypoints: list[GeoPosition]) -> WalkingRoute:
        if len(waypoints) < 2:
            raise ValueError("At least two waypoints are required to calculate a route")

        body = {
            "origin": _google_waypoint(waypoints[0]),
            "destination": _google_waypoint(waypoints[-1]),
            "intermediates": [
                _google_waypoint(waypoint) for waypoint in waypoints[1:-1]
            ],
            "travelMode": "WALK",
            "polylineEncoding": "GEO_JSON_LINESTRING",
            "polylineQuality": "OVERVIEW",
        }
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(
                self.endpoint,
                json=body,
                headers={
                    "Content-Type": "application/json",
                    "X-Goog-Api-Key": self.api_key,
                    "X-Goog-FieldMask": (
                        "routes.distanceMeters,routes.duration,"
                        "routes.polyline.geoJsonLinestring,"
                        "routes.legs.distanceMeters,routes.legs.duration,"
                        "routes.legs.startLocation,routes.legs.endLocation,"
                        "routes.warnings"
                    ),
                },
            )
            response.raise_for_status()
            return _parse_google_maps_response(response.json())


def _google_waypoint(position: GeoPosition) -> dict[str, Any]:
    return {
        "location": {
            "latLng": {
                "latitude": position.lat,
                "longitude": position.lon,
            }
        }
    }


def _parse_google_maps_response(data: JsonObject) -> WalkingRoute:
    routes = data.get("routes")
    if not isinstance(routes, list) or not routes:
        raise ValueError("Google Maps returned no walking route")
    route = routes[0]
    if not isinstance(route, Mapping):
        raise ValueError("Google Maps returned an invalid walking route")

    polyline = route.get("polyline")
    if not isinstance(polyline, Mapping):
        raise ValueError("Google Maps returned no route geometry")
    geometry = GeoJsonLineString.model_validate(polyline.get("geoJsonLinestring"))

    route_legs = route.get("legs")
    legs = [
        RouteLeg(
            distance_meters=leg.get("distanceMeters", 0),
            duration_seconds=_duration_seconds(leg.get("duration")),
            start=_google_position(leg.get("startLocation")),
            end=_google_position(leg.get("endLocation")),
        )
        for leg in route_legs or []
        if isinstance(leg, Mapping)
    ]
    warnings = route.get("warnings")
    return WalkingRoute(
        provider="google_maps",
        geometry=geometry,
        distance_meters=route.get("distanceMeters", 0),
        duration_seconds=_duration_seconds(route.get("duration")),
        legs=legs,
        warnings=[str(warning) for warning in warnings or []],
    )


def _duration_seconds(value: Any) -> float:
    if not isinstance(value, str) or not value.endswith("s"):
        raise ValueError("Google Maps returned an invalid route duration")
    return float(value[:-1])


def _google_position(value: Any) -> GeoPosition | None:
    if not isinstance(value, Mapping):
        return None
    lat_lng = value.get("latLng")
    if not isinstance(lat_lng, Mapping):
        return None
    lat = lat_lng.get("latitude")
    lon = lat_lng.get("longitude")
    if lat is None or lon is None:
        return None
    return GeoPosition(lat=lat, lon=lon)


__all__ = ["GoogleMapsRouter"]
