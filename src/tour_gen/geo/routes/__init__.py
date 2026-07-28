from typing import Protocol

from pydantic import BaseModel, Field

from tour_gen.geo.models import GeoJsonLineString, GeoPosition


class RouteLeg(BaseModel):
    distance_meters: float = Field(ge=0)
    duration_seconds: float = Field(ge=0)
    start: GeoPosition | None = None
    end: GeoPosition | None = None


class WalkingRoute(BaseModel):
    provider: str = Field(min_length=1)
    geometry: GeoJsonLineString
    distance_meters: float = Field(ge=0)
    duration_seconds: float = Field(ge=0)
    legs: list[RouteLeg] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class Router(Protocol):
    async def walking_route(self, waypoints: list[GeoPosition]) -> WalkingRoute: ...


__all__ = [
    "RouteLeg",
    "Router",
    "WalkingRoute",
]
