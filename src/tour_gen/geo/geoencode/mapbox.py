import os
from typing import Any

import httpx
from tour_gen.geo.geoencode import GeocodeResult


class MapboxGeocoder:
    endpoint = "https://api.mapbox.com/search/geocode/v6/forward"

    def __init__(self, access_token: str | None = None) -> None:
        self.access_token = access_token or os.environ.get("MAPBOX_ACCESS_TOKEN")
        if not self.access_token:
            raise RuntimeError("MAPBOX_ACCESS_TOKEN must be set in .env")

    async def geocode(self, query: str) -> GeocodeResult:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(
                self.endpoint,
                params={
                    "q": query,
                    "access_token": self.access_token,
                    "limit": 1,
                },
            )
            response.raise_for_status()
            return _parse_mapbox_response(query, response.json())


def _parse_mapbox_response(query: str, data: dict[str, Any]) -> GeocodeResult:
    features = data.get("features")
    if not features:
        return GeocodeResult(query=query)

    feature = features[0]
    coordinates = feature.get("geometry", {}).get("coordinates", [])
    if len(coordinates) < 2:
        return GeocodeResult(query=query)

    properties = feature.get("properties", {})
    return GeocodeResult(
        query=query,
        lat=coordinates[1],
        lon=coordinates[0],
        formatted_address=properties.get("full_address") or properties.get("name"),
    )
