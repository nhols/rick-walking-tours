import unittest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, Mock, call
from uuid import UUID, uuid4

from tour_gen.backend.models import (
    Tour,
    TourChapter,
    TourInput,
    TourOutputPayload,
    TourPlan,
    TourPlanPayload,
    TourStatus,
)
from tour_gen.backend.planning import plan_tour
from tour_gen.backend.ports import GeneratedPlan, WrittenTour
from tour_gen.backend.production import produce_tour


TOUR_ID = uuid4()
OWNER_ID = uuid4()
PLAN_ID = uuid4()
NOW = datetime.now(timezone.utc)
INPUT = TourInput(location="Test City", request="A history walk")
PLAN = TourPlanPayload(narrative_arc="Past to present", checkpoints=[])
OUTPUT = TourOutputPayload(tts_style={}, chapters=[])


def tour(status: TourStatus, approved_plan_id: UUID | None = None) -> Tour:
    return Tour(
        id=TOUR_ID,
        owner_id=OWNER_ID,
        status=status,
        input=INPUT,
        approved_plan_id=approved_plan_id,
        created_at=NOW,
        updated_at=NOW,
    )


def plan(revision: int = 1) -> TourPlan:
    return TourPlan(
        id=PLAN_ID,
        tour_id=TOUR_ID,
        revision=revision,
        payload=PLAN,
        created_at=NOW,
    )


class PlanningTest(unittest.IsolatedAsyncioTestCase):
    async def test_initial_plan_uses_tour_input(self) -> None:
        store = Mock()
        store.get_tour.return_value = tour(TourStatus.RESEARCHING)
        store.get_plan.return_value = None
        store.get_agent_messages.return_value = []
        generated = GeneratedPlan(payload=PLAN, new_messages=[{"role": "model"}])
        generator = Mock()
        generator.plan = AsyncMock(return_value=generated)

        await plan_tour(store, generator, TOUR_ID)

        generator.plan.assert_awaited_once_with(INPUT, INPUT.request, [])
        store.save_plan.assert_called_once_with(
            TOUR_ID,
            feedback=None,
            generated=generated,
        )

    async def test_revision_uses_feedback_and_history(self) -> None:
        store = Mock()
        store.get_tour.return_value = tour(TourStatus.RESEARCHING)
        store.get_plan.return_value = plan()
        store.get_agent_messages.return_value = [{"role": "model"}]
        generated = GeneratedPlan(payload=PLAN, new_messages=[])
        generator = Mock()
        generator.plan = AsyncMock(return_value=generated)

        await plan_tour(
            store,
            generator,
            TOUR_ID,
            plan_id=PLAN_ID,
            feedback="More industry",
        )

        generator.plan.assert_awaited_once_with(
            INPUT,
            "More industry",
            [{"role": "model"}],
        )

    async def test_failed_revision_restores_review_status(self) -> None:
        store = Mock()
        store.get_tour.return_value = tour(TourStatus.RESEARCHING)
        store.get_plan.return_value = plan()
        store.get_agent_messages.return_value = []
        generator = Mock()
        generator.plan = AsyncMock(side_effect=RuntimeError("model failed"))

        with self.assertRaisesRegex(RuntimeError, "model failed"):
            await plan_tour(
                store,
                generator,
                TOUR_ID,
                plan_id=PLAN_ID,
                feedback="Change it",
            )

        store.set_status.assert_called_once_with(
            TOUR_ID,
            TourStatus.AWAITING_REVIEW,
            {"error": "model failed"},
        )


class ProductionTest(unittest.IsolatedAsyncioTestCase):
    async def test_production_saves_written_then_completed_output(self) -> None:
        store = Mock()
        store.get_tour.return_value = tour(
            TourStatus.WRITING_CHAPTERS,
            approved_plan_id=PLAN_ID,
        )
        store.get_plan.return_value = plan()
        written = WrittenTour(title="Test Tour", output=OUTPUT)
        completed = TourOutputPayload(
            tts_style={},
            chapters=[
                TourChapter(
                    id=uuid4(),
                    checkpoint_id=uuid4(),
                    position=1,
                    title="Stop",
                    narration="Story",
                    audio_path="audio.wav",
                )
            ],
        )
        generator = Mock()
        generator.write = AsyncMock(return_value=written)
        generator.narrate = AsyncMock(return_value=completed)

        await produce_tour(store, generator, TOUR_ID, PLAN_ID)

        self.assertEqual(
            store.save_output.call_args_list,
            [
                call(
                    TOUR_ID,
                    PLAN_ID,
                    title="Test Tour",
                    output=OUTPUT,
                    status=TourStatus.GENERATING_AUDIO,
                ),
                call(
                    TOUR_ID,
                    PLAN_ID,
                    title="Test Tour",
                    output=completed,
                    status=TourStatus.READY,
                ),
            ],
        )


if __name__ == "__main__":
    unittest.main()
