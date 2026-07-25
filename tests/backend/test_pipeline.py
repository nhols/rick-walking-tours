import unittest

from pydantic_ai import BinaryContent, ModelMessage
from pydantic_ai.messages import ModelRequest, UserPromptPart

from tour_gen.geo.distance_matrix import GeocodedPlace
from tour_gen.geo.static_map import checkpoint_map_url
from tour_gen.pipeline import _without_binary_content


class PlanningPipelineTest(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
