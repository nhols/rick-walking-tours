import unittest
from datetime import datetime, timezone
from typing import cast
from unittest.mock import Mock
from uuid import uuid4

from pydantic_ai import ModelRetry

from tour_gen.agents.tour_assistant import (
    MAX_RESPONSE_WORDS,
    TourAssistantContext,
    TourAssistantDeps,
    add_tour_context_instruction,
    validate_response_length,
)
from tour_gen.backend.models import (
    TourCheckpoint,
    Tour,
    TourChapter,
    TourInput,
    TourOutputPayload,
    TourPlan,
    TourPlanPayload,
    TourStatus,
)
from tour_gen.geo.models import GeoJsonLineString
from tour_gen.geo.routes import RouteLeg, WalkingRoute


TOUR_ID = uuid4()
PLAN_ID = uuid4()
CHAPTER_ID = uuid4()
CHECKPOINT_ID = uuid4()
SECOND_CHAPTER_ID = uuid4()
SECOND_CHECKPOINT_ID = uuid4()
NOW = datetime.now(timezone.utc)


def assistant_context(*, stored_duration: float | None = 240) -> TourAssistantContext:
    chapter = TourChapter(
        id=CHAPTER_ID,
        checkpoint_id=CHECKPOINT_ID,
        position=1,
        title="Test chapter",
        narration="A chapter about the test location.",
        duration_seconds=stored_duration,
    )
    second_chapter = TourChapter(
        id=SECOND_CHAPTER_ID,
        checkpoint_id=SECOND_CHECKPOINT_ID,
        position=2,
        title="Second chapter",
        narration="The story continues at the second location.",
        duration_seconds=180,
    )
    tour = Tour(
        id=TOUR_ID,
        owner_id=uuid4(),
        status=TourStatus.READY,
        title="Test tour",
        input=TourInput(location="Test City", request="A history walk"),
        approved_plan_id=PLAN_ID,
        created_at=NOW,
        updated_at=NOW,
    )
    plan = TourPlan(
        id=PLAN_ID,
        tour_id=TOUR_ID,
        revision=1,
        payload=TourPlanPayload(
            narrative_arc="Past to present",
            checkpoints=[
                TourCheckpoint(
                    id=CHECKPOINT_ID,
                    position=1,
                    title="Test chapter",
                    description="The first stop",
                    route_reasoning="Start here",
                    distance_tool_place_name="First place",
                    lat=55.95,
                    lon=-3.19,
                ),
                TourCheckpoint(
                    id=SECOND_CHECKPOINT_ID,
                    position=2,
                    title="Second chapter",
                    description="The second stop",
                    route_reasoning="Continue here",
                    distance_tool_place_name="Second place",
                    lat=55.96,
                    lon=-3.18,
                ),
            ],
            route=WalkingRoute(
                provider="mapbox",
                geometry=GeoJsonLineString(
                    coordinates=[(-3.19, 55.95), (-3.18, 55.96)]
                ),
                distance_meters=750,
                duration_seconds=660,
                legs=[RouteLeg(distance_meters=750, duration_seconds=660)],
            ),
        ),
        created_at=NOW,
    )
    return TourAssistantContext(
        tour=tour,
        approved_plan=plan,
        output=TourOutputPayload(tts_style={}, chapters=[chapter, second_chapter]),
        selected_chapter=chapter,
    )


def deps(*, stored_duration: float | None = 240) -> TourAssistantDeps:
    loader = Mock()
    loader.load.return_value = assistant_context(stored_duration=stored_duration)
    return TourAssistantDeps(
        tour_id=TOUR_ID,
        selected_chapter_id=CHAPTER_ID,
        chapter_playback_seconds=60,
        context_loader=loader,
    )


class TourAssistantInstructionTest(unittest.TestCase):
    def test_context_is_readable_and_contains_no_ids(self) -> None:
        assistant_deps = deps()
        run_context = Mock(deps=assistant_deps)

        instruction = add_tour_context_instruction(run_context)

        self.assertIn("Title: Test tour", instruction)
        self.assertIn("Location: Test City", instruction)
        self.assertIn(
            "Stop 1 — Test chapter\nNarration:\n"
            "A chapter about the test location.",
            instruction,
        )
        self.assertIn(
            "Stop 2 — Second chapter\nNarration:\n"
            "The story continues at the second location.",
            instruction,
        )
        self.assertIn(
            "Stop 1 — Test chapter → Stop 2 — Second chapter: 750 m, 11 min",
            instruction,
        )
        self.assertIn("Total walking route: 750 m, 11 min", instruction)
        self.assertIn("Selected chapter: Stop 1 — Test chapter", instruction)
        self.assertIn("Playback: 1:00 of 4:00 (25.0%, approximate).", instruction)
        self.assertNotIn(str(TOUR_ID), instruction)
        self.assertNotIn(str(PLAN_ID), instruction)
        self.assertNotIn(str(CHAPTER_ID), instruction)
        self.assertNotIn(str(CHECKPOINT_ID), instruction)
        loader = cast(Mock, assistant_deps.context_loader)
        loader.load.assert_called_once_with(
            TOUR_ID,
            CHAPTER_ID,
        )

    def test_progress_is_unknown_when_db_duration_is_missing(self) -> None:
        assistant_deps = deps(stored_duration=None)
        run_context = Mock(deps=assistant_deps)

        instruction = add_tour_context_instruction(run_context)

        self.assertIn("Playback: 1:00; chapter duration unavailable.", instruction)

    def test_context_is_only_loaded_once_across_retries(self) -> None:
        assistant_deps = deps()
        run_context = Mock(deps=assistant_deps)

        add_tour_context_instruction(run_context)
        add_tour_context_instruction(run_context)

        loader = cast(Mock, assistant_deps.context_loader)
        loader.load.assert_called_once()


class TourAssistantValidationTest(unittest.TestCase):
    def test_short_response_is_stripped_and_returned(self) -> None:
        self.assertEqual(
            validate_response_length(Mock(), "  A concise answer.  "),
            "A concise answer.",
        )

    def test_empty_response_retries(self) -> None:
        with self.assertRaises(ModelRetry):
            validate_response_length(Mock(), "   ")

    def test_long_response_retries(self) -> None:
        with self.assertRaises(ModelRetry):
            validate_response_length(Mock(), "word " * (MAX_RESPONSE_WORDS + 1))


class TourAssistantDepsTest(unittest.TestCase):
    def test_negative_playback_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "must not be negative"):
            TourAssistantDeps(
                tour_id=TOUR_ID,
                selected_chapter_id=CHAPTER_ID,
                chapter_playback_seconds=-1,
                context_loader=Mock(),
            )


if __name__ == "__main__":
    unittest.main()
