import os
from collections.abc import Mapping
from typing import Any, TypeAlias

import httpx
from tour_gen.geo.geoencode import GeocodeResult, GeoPosition


JsonObject: TypeAlias = Mapping[str, Any]


class MapboxGeocoder:
    endpoint = "https://api.mapbox.com/search/geocode/v6/forward"

    def __init__(self, access_token: str | None = None) -> None:
        resolved_access_token = access_token or os.environ.get("MAPBOX_ACCESS_TOKEN")
        if not resolved_access_token:
            raise RuntimeError("MAPBOX_ACCESS_TOKEN must be set in .env")
        self.access_token: str = resolved_access_token

    async def geocode(
        self,
        query: str,
        *,
        bias_position: GeoPosition | None = None,
    ) -> GeocodeResult:
        params: dict[str, str | int] = {
            "q": query,
            "access_token": self.access_token,
            "limit": 1,
        }
        if bias_position is not None:
            params["proximity"] = f"{bias_position.lon},{bias_position.lat}"

        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(
                self.endpoint,
                params=params,
            )
            response.raise_for_status()
            return _parse_mapbox_response(query, response.json())


def _parse_mapbox_response(query: str, data: JsonObject) -> GeocodeResult:
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
