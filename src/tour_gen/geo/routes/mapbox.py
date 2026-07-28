import os
from collections.abc import Mapping
from typing import Any, TypeAlias

import httpx

from tour_gen.geo.models import GeoJsonLineString, GeoPosition
from tour_gen.geo.routes import RouteLeg, WalkingRoute


JsonObject: TypeAlias = Mapping[str, Any]


class MapboxRouter:
    endpoint = "https://api.mapbox.com/directions/v5/mapbox/walking"

    def __init__(self, access_token: str | None = None) -> None:
        resolved_access_token = access_token or os.environ.get("MAPBOX_ACCESS_TOKEN")
        if not resolved_access_token:
            raise RuntimeError("MAPBOX_ACCESS_TOKEN must be set in .env")
        self.access_token: str = resolved_access_token

    async def walking_route(self, waypoints: list[GeoPosition]) -> WalkingRoute:
        if len(waypoints) < 2:
            raise ValueError("At least two waypoints are required to calculate a route")

        coordinates = ";".join(
            f"{waypoint.lon},{waypoint.lat}" for waypoint in waypoints
        )
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(
                f"{self.endpoint}/{coordinates}",
                params={
                    "access_token": self.access_token,
                    "geometries": "geojson",
                    "overview": "simplified",
                    "steps": "false",
                },
            )
            response.raise_for_status()
            return _parse_mapbox_response(response.json())


def _parse_mapbox_response(data: JsonObject) -> WalkingRoute:
    if data.get("code") != "Ok":
        raise ValueError(str(data.get("message") or data.get("code") or "No route"))

    routes = data.get("routes")
    if not isinstance(routes, list) or not routes:
        raise ValueError("Mapbox returned no walking route")
    route = routes[0]
    if not isinstance(route, Mapping):
        raise ValueError("Mapbox returned an invalid walking route")

    geometry = GeoJsonLineString.model_validate(route.get("geometry"))
    snapped_waypoints = _mapbox_waypoints(data.get("waypoints"))
    route_legs = route.get("legs")
    legs = [
        RouteLeg(
            distance_meters=leg.get("distance", 0),
            duration_seconds=leg.get("duration", 0),
            start=(
                snapped_waypoints[index]
                if index < len(snapped_waypoints)
                else None
            ),
            end=(
                snapped_waypoints[index + 1]
                if index + 1 < len(snapped_waypoints)
                else None
            ),
        )
        for index, leg in enumerate(route_legs or [])
        if isinstance(leg, Mapping)
    ]
    return WalkingRoute(
        provider="mapbox",
        geometry=geometry,
        distance_meters=route.get("distance", 0),
        duration_seconds=route.get("duration", 0),
        legs=legs,
    )


def _mapbox_waypoints(value: Any) -> list[GeoPosition]:
    if not isinstance(value, list):
        return []
    positions: list[GeoPosition] = []
    for waypoint in value:
        if not isinstance(waypoint, Mapping):
            continue
        location = waypoint.get("location")
        if not isinstance(location, list) or len(location) < 2:
            continue
        positions.append(GeoPosition(lon=location[0], lat=location[1]))
    return positions


__all__ = ["MapboxRouter"]
