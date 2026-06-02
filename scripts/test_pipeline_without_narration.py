import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import Any

import logfire


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from tour_gen.geo.geoencode.mapbox import MapboxGeocoder
from tour_gen.pipeline import plan_route, research_checkpoints, write_chapters


DEFAULT_PROMPT = (
    "Create a walking tour of Wandsworth Common in southwest London, focusing "
    "on its history and modern-day life. Include 8-10 real, visitable locations "
    "around the common and nearby streets, balancing historic context, local "
    "character, nature, transport, community spaces, and present-day amenities."
)
DEFAULT_LOCATION = "Wandsworth Common, southwest London"

logger = logging.getLogger(__name__)


async def main() -> None:
    args = parse_args()

    with logfire.span(
        "Test tour pipeline without narration",
        prompt=args.prompt,
        location=args.location,
        has_voice_style=args.voice_style is not None,
    ):
        logger.info(
            "Testing tour pipeline without narration prompt=%s location=%s",
            args.prompt,
            args.location,
        )

        with logfire.span("Research checkpoints"):
            checkpoint_research, checkpoint_coordinates = await research_checkpoints(
                args.prompt,
                location=args.location,
                geocoder=MapboxGeocoder(),
            )
            print_stage(
                "checkpoint_research",
                checkpoint_research.model_dump(mode="json"),
            )
            print_stage(
                "checkpoint_coordinates",
                [coordinate.model_dump(mode="json") for coordinate in checkpoint_coordinates],
            )

        with logfire.span("Plan route"):
            route_plan = await plan_route(checkpoint_research)
            print_stage("route_plan", route_plan.model_dump(mode="json"))

        with logfire.span("Write chapters"):
            chapters = await write_chapters(route_plan, voice_style=args.voice_style)
            print_stage("chapters", chapters.model_dump(mode="json"))

        print_stage(
            "summary",
            {
                "checkpoint_count": len(checkpoint_research.proposals),
                "coordinate_count": len(checkpoint_coordinates),
                "ordered_checkpoint_count": len(route_plan.ordered_checkpoints),
                "chapter_count": len(chapters.chapters),
                "narration_skipped": True,
            },
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the tour generation pipeline through chapter writing, skipping narration/TTS.",
    )
    parser.add_argument(
        "--prompt",
        default=DEFAULT_PROMPT,
        help=f"Tour request to test. Defaults to: {DEFAULT_PROMPT!r}",
    )
    parser.add_argument(
        "--location",
        default=DEFAULT_LOCATION,
        help=f"Location for research and geocoding. Defaults to: {DEFAULT_LOCATION!r}",
    )
    parser.add_argument(
        "--voice-style",
        default=None,
        help="Optional voice style guide to pass into chapter writing.",
    )
    return parser.parse_args()


def print_stage(name: str, data: Any) -> None:
    print(f"\n=== {name} ===")
    print(json.dumps(data, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())
