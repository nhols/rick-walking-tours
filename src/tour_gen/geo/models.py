from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class GeoPosition(BaseModel):
    model_config = ConfigDict(frozen=True)

    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)


class GeoJsonLineString(BaseModel):
    type: Literal["LineString"] = "LineString"
    coordinates: list[tuple[float, float]] = Field(min_length=2)

    @field_validator("coordinates")
    @classmethod
    def validate_coordinates(
        cls,
        coordinates: list[tuple[float, float]],
    ) -> list[tuple[float, float]]:
        for lon, lat in coordinates:
            if not -180 <= lon <= 180 or not -90 <= lat <= 90:
                raise ValueError("Route coordinates must be valid longitude/latitude pairs")
        return coordinates


__all__ = ["GeoJsonLineString", "GeoPosition"]
