from typing import TypedDict

from tour_gen.geo.distance_matrix import DistanceMatrixEntry, GeocodedPlace


class DuplicateCoordinateGroup(TypedDict):
    lat: float
    lon: float
    place_names: list[str]


class FormattedDistance(TypedDict):
    from_place: str
    to_place: str
    distance_km: float


class FormattedGeocodedPlace(TypedDict):
    place_name: str
    lat: float
    lon: float
    formatted_address: str | None


def _duplicate_coordinate_groups(
    place_names: list[str],
    geocoded_places: dict[str, GeocodedPlace],
) -> list[DuplicateCoordinateGroup]:
    places_by_coordinate: dict[tuple[float, float], list[str]] = {}
    for place_name in place_names:
        place = geocoded_places.get(place_name)
        if place is None:
            continue
        places_by_coordinate.setdefault((place.lat, place.lon), []).append(place_name)

    return [
        {
            "lat": coordinate[0],
            "lon": coordinate[1],
            "place_names": sorted(coordinate_place_names),
        }
        for coordinate, coordinate_place_names in sorted(places_by_coordinate.items())
        if len(coordinate_place_names) > 1
    ]


def _format_distances(
    distances: list[DistanceMatrixEntry],
) -> list[FormattedDistance]:
    return [
        {
            "from_place": distance.from_place,
            "to_place": distance.to_place,
            "distance_km": distance.distance_km,
        }
        for distance in sorted(
            distances,
            key=lambda distance: distance.distance_km,
            reverse=True,
        )
    ]


def _format_geocoded_places(
    places: dict[str, GeocodedPlace],
) -> list[FormattedGeocodedPlace]:
    return [
        {
            "place_name": place.place_name,
            "lat": place.lat,
            "lon": place.lon,
            "formatted_address": place.formatted_address,
        }
        for place in sorted(places.values(), key=lambda place: place.place_name)
    ]
