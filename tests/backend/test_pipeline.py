import asyncio
import unittest
from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock, Mock, patch

from pydantic_ai import BinaryContent, ModelMessage, ModelRetry, RunContext
from pydantic_ai.messages import ModelRequest, UserPromptPart

from tour_gen.agents.checkpoint_researcher import (
    CheckpointProposal,
    CheckpointResearchDeps,
    CheckpointResearchOutput,
    validate_checkpoint_output,
)
from tour_gen.agents.checkpoint_researcher.tools import estimate_place_distances
from tour_gen.geo.distance_matrix import GeocodedPlace
from tour_gen.geo.geoencode import Geocoder, GeoPosition
from tour_gen.geo.geoencode.google_maps import GoogleMapsGeocoder
from tour_gen.geo.geoencode.mapbox import MapboxGeocoder
from tour_gen.geo.static_map import checkpoint_map_url
from tour_gen.pipeline import _without_binary_content


class PlanningPipelineTest(unittest.TestCase):
    def test_checkpoint_count_must_be_within_requested_range(self) -> None:
        context = cast(
            RunContext[CheckpointResearchDeps],
            SimpleNamespace(deps=SimpleNamespace(min_stops=3, max_stops=4)),
        )

        for count in (2, 5):
            with self.subTest(count=count), self.assertRaisesRegex(
                ModelRetry,
                f"returned {count}",
            ):
                validate_checkpoint_output(
                    context,
                    CheckpointResearchOutput(
                        narrative_arc="Test route",
                        response_to_user="I created the requested route.",
                        ordered_checkpoints=[
                            CheckpointProposal(
                                title=f"Stop {index}",
                                brief_description="Description",
                                route_reasoning="Reason",
                                distance_tool_place_name=f"Place {index}",
                            )
                            for index in range(count)
                        ],
                    ),
                )

    def test_checkpoint_map_contains_numbered_pins(self) -> None:
        url = checkpoint_map_url(
            [
                GeocodedPlace(
                    place_name="Library",
                    query="Library",
                    lat=51.5,
                    lon=-0.1,
                ),
                GeocodedPlace(
                    place_name="Clock",
                    query="Clock",
                    lat=51.51,
                    lon=-0.11,
                ),
            ]
        )

        self.assertIn("pin-s-1+d9573f(-0.1,51.5)", url)
        self.assertIn("pin-s-2+d9573f(-0.11,51.51)", url)
        self.assertTrue(url.endswith("/auto/800x600@2x"))

    def test_binary_map_is_removed_from_persisted_history(self) -> None:
        messages: list[ModelMessage] = [
            ModelRequest(
                parts=[
                    UserPromptPart(
                        content=[
                            "Numbered checkpoint map",
                            BinaryContent(data=b"png", media_type="image/png"),
                        ]
                    )
                ]
            )
        ]

        cleaned = _without_binary_content(messages)

        request = cleaned[0]
        assert isinstance(request, ModelRequest)
        part = request.parts[0]
        assert isinstance(part, UserPromptPart)
        self.assertEqual(part.content, ["Numbered checkpoint map"])


class DistanceToolTest(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_too_many_places_before_geocoding(self) -> None:
        geocode = AsyncMock()
        geocoder = cast(Geocoder, SimpleNamespace(geocode=geocode))
        context = cast(
            RunContext[CheckpointResearchDeps],
            SimpleNamespace(
                deps=CheckpointResearchDeps(
                    location="Test City",
                    geocoder=geocoder,
                    max_stops=2,
                )
            ),
        )

        with (
            patch(
                "tour_gen.agents.checkpoint_researcher.tools."
                "build_crow_flies_distance_matrix_result",
                new=AsyncMock(),
            ) as build_matrix,
            self.assertRaisesRegex(ModelRetry, "at most 2 places"),
        ):
            await estimate_place_distances(context, ["One", "Two", "Three"])

        geocode.assert_not_awaited()
        build_matrix.assert_not_awaited()

    async def test_google_geocoder_caches_query_and_bias(self) -> None:
        geocoder = GoogleMapsGeocoder("test-key")
        bias = GeoPosition(lat=51.5, lon=-0.1)
        response = Mock()
        response.json.return_value = {
            "places": [{"location": {"latitude": 51.5, "longitude": -0.1}}]
        }
        client = AsyncMock()
        client.__aenter__.return_value = client
        client.post.return_value = response

        with patch(
            "tour_gen.geo.geoencode.google_maps.httpx.AsyncClient",
            return_value=client,
        ):
            first, second = await asyncio.gather(
                geocoder.geocode("Library", bias_position=bias),
                geocoder.geocode("Library", bias_position=bias),
            )
            third = await geocoder.geocode("Library", bias_position=bias)

        client.post.assert_awaited_once()
        self.assertIs(first, second)
        self.assertIs(second, third)

    async def test_mapbox_geocoder_caches_query_and_bias(self) -> None:
        geocoder = MapboxGeocoder("test-token")
        bias = GeoPosition(lat=51.5, lon=-0.1)
        response = Mock()
        response.json.return_value = {
            "features": [
                {
                    "geometry": {"coordinates": [-0.1, 51.5]},
                    "properties": {},
                }
            ]
        }
        client = AsyncMock()
        client.__aenter__.return_value = client
        client.get.return_value = response

        with patch(
            "tour_gen.geo.geoencode.mapbox.httpx.AsyncClient",
            return_value=client,
        ):
            first = await geocoder.geocode("Library", bias_position=bias)
            second = await geocoder.geocode("Library", bias_position=bias)

        client.get.assert_awaited_once()
        self.assertIs(first, second)


if __name__ == "__main__":
    unittest.main()
