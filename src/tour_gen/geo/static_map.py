import os

import httpx

from tour_gen.geo.distance_matrix import GeocodedPlace


MAPBOX_STATIC_IMAGES_URL = (
    "https://api.mapbox.com/styles/v1/mapbox/streets-v12/static"
)


async def render_checkpoint_map(places: list[GeocodedPlace]) -> bytes:
    access_token = os.environ.get("MAPBOX_ACCESS_TOKEN")
    if not access_token:
        raise RuntimeError("MAPBOX_ACCESS_TOKEN must be set in .env")
    url = checkpoint_map_url(places)
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.get(
            url,
            params={"access_token": access_token, "padding": 80},
        )
        response.raise_for_status()
        return response.content


def checkpoint_map_url(places: list[GeocodedPlace]) -> str:
    if not places:
        raise ValueError("At least one place is required to render a map")
    pins = ",".join(
        f"pin-s-{index}+d9573f({place.lon},{place.lat})"
        for index, place in enumerate(places, start=1)
    )
    return f"{MAPBOX_STATIC_IMAGES_URL}/{pins}/auto/800x600@2x"
