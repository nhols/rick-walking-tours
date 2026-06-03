from typing import Protocol

from pydantic import BaseModel, Field


class GeocodeResult(BaseModel):
    query: str
    lat: float | None = Field(default=None, ge=-90, le=90)
    lon: float | None = Field(default=None, ge=-180, le=180)
    formatted_address: str | None = None


class GeoPosition(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)


class Geocoder(Protocol):
    async def geocode(
        self,
        query: str,
        *,
        bias_position: GeoPosition | None = None,
    ) -> GeocodeResult: ...


__all__ = [
    "GeocodeResult",
    "GeoPosition",
    "Geocoder",
]
