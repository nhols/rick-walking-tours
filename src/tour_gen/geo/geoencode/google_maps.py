import os
from collections.abc import Mapping
from typing import Any, TypeAlias

import httpx
from async_lru import alru_cache

from tour_gen.geo.geoencode import GeocodeResult, GeoPosition


JsonObject: TypeAlias = Mapping[str, Any]


class GoogleMapsGeocoder:
    endpoint = "https://places.googleapis.com/v1/places:searchText"

    def __init__(
        self,
        api_key: str | None = None,
        *,
        bias_radius_m: float = 5_000,
        language_code: str = "en",
    ) -> None:
        resolved_api_key = api_key or os.environ.get("GOOGLE_MAPS_API_KEY")
        if not resolved_api_key:
            raise RuntimeError("GOOGLE_MAPS_API_KEY must be set in .env")
        self.api_key: str = resolved_api_key
        self.bias_radius_m: float = bias_radius_m
        self.language_code: str = language_code

    @alru_cache(maxsize=128)
    async def geocode(
        self,
        query: str,
        *,
        bias_position: GeoPosition | None = None,
    ) -> GeocodeResult:
        body: dict[str, Any] = {
            "textQuery": query,
            "pageSize": 1,
            "languageCode": self.language_code,
        }
        if bias_position is not None:
            body["locationBias"] = {
                "circle": {
                    "center": {
                        "latitude": bias_position.lat,
                        "longitude": bias_position.lon,
                    },
                    "radius": self.bias_radius_m,
                }
            }

        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(
                self.endpoint,
                json=body,
                headers={
                    "Content-Type": "application/json",
                    "X-Goog-Api-Key": self.api_key,
                    "X-Goog-FieldMask": (
                        "places.displayName,places.formattedAddress,"
                        "places.location"
                    ),
                },
            )
            response.raise_for_status()
            return _parse_places_text_search_response(query, response.json())


def _parse_places_text_search_response(
    query: str,
    data: JsonObject,
) -> GeocodeResult:
    places = data.get("places")
    if not places:
        return GeocodeResult(query=query)

    place = places[0]
    location = place.get("location", {})
    lat = location.get("latitude")
    lon = location.get("longitude")
    if lat is None or lon is None:
        return GeocodeResult(query=query)

    display_name = place.get("displayName", {})
    return GeocodeResult(
        query=query,
        lat=lat,
        lon=lon,
        formatted_address=place.get("formattedAddress") or display_name.get("text"),
    )
