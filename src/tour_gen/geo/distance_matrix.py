import asyncio
import math

from pydantic import BaseModel, Field

from tour_gen.geo.geoencode import GeocodeResult, Geocoder


EARTH_RADIUS_KM = 6_371.0088


class DistanceMatrixEntry(BaseModel):
    from_place: str = Field(min_length=1)
    to_place: str = Field(min_length=1)
    distance_km: float = Field(ge=0)


class GeocodedPlace(BaseModel):
    place_name: str = Field(min_length=1)
    query: str = Field(min_length=1)
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    formatted_address: str | None = None


class CrowFliesDistanceMatrixResult(BaseModel):
    geocoded_places: list[GeocodedPlace]
    distances: list[DistanceMatrixEntry]


async def build_crow_flies_distance_matrix(
    *,
    place_names: list[str],
    location: str,
    geocoder: Geocoder,
) -> list[DistanceMatrixEntry]:
    result = await build_crow_flies_distance_matrix_result(
        place_names=place_names,
        location=location,
        geocoder=geocoder,
    )
    return result.distances


async def build_crow_flies_distance_matrix_result(
    *,
    place_names: list[str],
    location: str,
    geocoder: Geocoder,
) -> CrowFliesDistanceMatrixResult:
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
    for from_index, from_place in enumerate(coordinates):
        for to_place in coordinates[from_index + 1 :]:
            entries.append(
                DistanceMatrixEntry(
                    from_place=from_place.place_name,
                    to_place=to_place.place_name,
                    distance_km=round(
                        _haversine_km(
                            from_place.lat,
                            from_place.lon,
                            to_place.lat,
                            to_place.lon,
                        ),
                        2,
                    ),
                )
            )
    return CrowFliesDistanceMatrixResult(
        geocoded_places=coordinates,
        distances=entries,
    )


def _require_coordinates(
    place_name: str,
    result: GeocodeResult,
) -> GeocodedPlace:
    if result.lat is None or result.lon is None:
        raise ValueError(f"Could not geocode place: {place_name}")
    return GeocodedPlace(
        place_name=place_name,
        query=result.query,
        lat=result.lat,
        lon=result.lon,
        formatted_address=result.formatted_address,
    )


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
