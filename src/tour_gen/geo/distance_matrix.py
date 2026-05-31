import asyncio
import math

from pydantic import BaseModel, Field

from tour_gen.geo.geoencode import GeocodeResult, Geocoder


EARTH_RADIUS_KM = 6_371.0088


class DistanceMatrixEntry(BaseModel):
    from_place: str = Field(min_length=1)
    to_place: str = Field(min_length=1)
    distance_km: float = Field(ge=0)


async def build_crow_flies_distance_matrix(
    *,
    place_names: list[str],
    location: str,
    geocoder: Geocoder,
) -> list[DistanceMatrixEntry]:
    geocoded_places = await asyncio.gather(
        *[
            geocoder.geocode(f"{place_name}, {location}")
            for place_name in place_names
        ]
    )
    coordinates = [
        _require_coordinates(place_name, geocoded_place)
        for place_name, geocoded_place in zip(place_names, geocoded_places, strict=True)
    ]

    entries: list[DistanceMatrixEntry] = []
    for from_index, (from_place, from_lat, from_lon) in enumerate(coordinates):
        for to_place, to_lat, to_lon in coordinates[from_index + 1 :]:
            entries.append(
                DistanceMatrixEntry(
                    from_place=from_place,
                    to_place=to_place,
                    distance_km=round(
                        _haversine_km(from_lat, from_lon, to_lat, to_lon),
                        2,
                    ),
                )
            )
    return entries


def _require_coordinates(
    place_name: str,
    result: GeocodeResult,
) -> tuple[str, float, float]:
    if result.lat is None or result.lon is None:
        raise ValueError(f"Could not geocode place: {place_name}")
    return place_name, result.lat, result.lon


def _haversine_km(
    lat_a: float,
    lon_a: float,
    lat_b: float,
    lon_b: float,
) -> float:
    lat_a_rad = math.radians(lat_a)
    lat_b_rad = math.radians(lat_b)
    delta_lat = math.radians(lat_b - lat_a)
    delta_lon = math.radians(lon_b - lon_a)

    chord = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(lat_a_rad)
        * math.cos(lat_b_rad)
        * math.sin(delta_lon / 2) ** 2
    )
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(chord))
