import unittest
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from tour_gen.agents.chapter_writer import Chapter, ChapterWriterOutput, TTSStyle
from tour_gen.agents.checkpoint_researcher import (
    CheckpointProposal,
    CheckpointResearchOutput,
)
from tour_gen.backend.app import create_app
from tour_gen.backend.models import (
    Tour,
    TourInput,
    TourOutput,
    TourOutputPayload,
    TourPlan,
    TourPlanPayload,
    TourStatus,
    TourSummary,
)
from tour_gen.pipeline import CheckpointCoordinates, CheckpointResearchRun
from tour_gen.tts.narration import NarratedChapter, NarrationOutput
from tour_gen.tts.provider import TTSProvider, TTSRequest, TTSResult


OWNER_ID = UUID("00000000-0000-0000-0000-000000000001")


def now() -> datetime:
    return datetime.now(timezone.utc)


class UnusedGeocoder:
    async def geocode(self, query: str, *, bias_position=None):
        raise AssertionError("The fake pipeline should not call the geocoder")


class UnusedTTSProvider(TTSProvider):
    async def synthesize(self, request: TTSRequest) -> TTSResult:
        raise AssertionError("The fake pipeline should not call the TTS provider")


class FakePipeline:
    def __init__(self) -> None:
        self.write_calls = 0
        self.narrate_calls = 0
        self.research_calls: list[dict[str, Any]] = []

    async def research_checkpoints(
        self,
        *,
        prompt,
        location,
        geocoder,
        min_stops=2,
        max_stops=10,
        max_checkpoint_distance_km=10.0,
        message_history=None,
    ):
        history = list(message_history or [])
        self.research_calls.append(
            {
                "prompt": prompt,
                "message_history": history,
                "min_stops": min_stops,
                "max_stops": max_stops,
                "max_checkpoint_distance_km": max_checkpoint_distance_km,
            }
        )
        return CheckpointResearchRun(
            output=CheckpointResearchOutput(
                ordered_checkpoints=[
                    CheckpointProposal(
                        title="Old Library",
                        brief_description="The story begins among historic books.",
                        route_reasoning="Introduces the tour's theme.",
                        distance_tool_place_name="Old Library, Test City",
                    ),
                    CheckpointProposal(
                        title="Clock Tower",
                        brief_description="A landmark that closes the story.",
                        route_reasoning="Provides a natural finale.",
                        distance_tool_place_name="Clock Tower, Test City",
                    ),
                ],
                narrative_arc="From the written past to the city's public clock.",
            ),
            coordinates=[
                CheckpointCoordinates(
                    place_name="Old Library, Test City",
                    lat=51.5,
                    lon=-0.1,
                    formatted_address="1 Library Lane",
                ),
                CheckpointCoordinates(
                    place_name="Clock Tower, Test City",
                    lat=51.501,
                    lon=-0.101,
                    formatted_address="2 Clock Street",
                ),
            ],
            new_agent_messages=[{"prompt": prompt}],
        )

    async def write_chapters(self, *, plan, location, voice_style=None):
        self.write_calls += 1
        return ChapterWriterOutput(
            tour_title="Books and Bells",
            tts_style=TTSStyle(
                scene_setting="A calm city walk",
                tone="Warm and curious",
                pace="Unhurried",
            ),
            chapters=[
                Chapter(title=item.title, narration=f"Narration for {item.title}.")
                for item in plan.ordered_checkpoints
            ],
        )

    async def narrate_tour(
        self,
        *,
        chapters,
        tts_provider,
        voice,
        model=None,
        audio_format="wav",
    ):
        self.narrate_calls += 1
        return NarrationOutput(
            chapters=[
                NarratedChapter(
                    title=chapter.title,
                    narration=chapter.narration,
                    audio=f"audio-{position}".encode(),
                    media_type="audio/wav",
                    audio_format="wav",
                    voice=voice,
                    model=model or "fake-tts",
                    duration_seconds=12.5,
                )
                for position, chapter in enumerate(chapters.chapters, start=1)
            ]
        )


class MemoryArtifactStore:
    def __init__(self) -> None:
        self.files: dict[str, bytes] = {}

    def save_audio(
        self,
        *,
        owner_id,
        tour_id,
        position,
        audio_format,
        media_type,
        audio,
    ) -> str:
        path = f"{owner_id}/{tour_id}/{position:03d}.{audio_format}"
        self.files[path] = audio
        return path

    def create_signed_url(self, path: str, *, expires_in: int = 3_600) -> str:
        return f"https://storage.test/{path}?expires={expires_in}"


class MemoryTourRepository:
    def __init__(self) -> None:
        self.tours: dict[UUID, Tour] = {}
        self.plans: dict[UUID, TourPlan] = {}
        self.outputs: dict[tuple[UUID, UUID], TourOutput] = {}
        self.status_events: list[tuple[UUID, TourStatus, dict[str, Any] | None]] = []

    def create_tour(self, owner_id: UUID, data: TourInput) -> Tour:
        timestamp = now()
        tour = Tour(
            id=uuid4(),
            owner_id=owner_id,
            status=TourStatus.RESEARCHING,
            input=data,
            created_at=timestamp,
            updated_at=timestamp,
        )
        self.tours[tour.id] = tour
        return self.set_status(tour.id, TourStatus.RESEARCHING)

    def get_tour(self, tour_id: UUID, owner_id: UUID | None = None) -> Tour | None:
        tour = self.tours.get(tour_id)
        if tour is not None and owner_id is not None and tour.owner_id != owner_id:
            return None
        return tour

    def list_tours(self, owner_id: UUID) -> list[TourSummary]:
        return [
            TourSummary.model_validate(tour.model_dump())
            for tour in self.tours.values()
            if tour.owner_id == owner_id
        ]

    def set_status(
        self,
        tour_id: UUID,
        status: TourStatus,
        details: dict[str, Any] | None = None,
    ) -> Tour:
        tour = self.tours[tour_id]
        tour = tour.model_copy(update={"status": status, "updated_at": now()})
        self.tours[tour_id] = tour
        self.status_events.append((tour_id, status, details))
        return tour

    def get_plans(self, tour_id: UUID) -> list[TourPlan]:
        return sorted(
            (plan for plan in self.plans.values() if plan.tour_id == tour_id),
            key=lambda plan: plan.revision,
        )

    def get_plan(self, tour_id: UUID, plan_id: UUID | None = None) -> TourPlan | None:
        plans = [
            plan
            for plan in self.get_plans(tour_id)
            if plan_id is None or plan.id == plan_id
        ]
        return plans[-1] if plans else None

    def get_agent_messages(self, tour_id: UUID) -> list[dict[str, Any]]:
        return [
            message
            for plan in self.get_plans(tour_id)
            for message in plan.new_agent_messages
        ]

    def persist_plan(
        self,
        tour_id: UUID,
        *,
        feedback: str | None,
        payload: TourPlanPayload,
        new_agent_messages: list[dict[str, Any]],
    ) -> TourPlan:
        plan = TourPlan(
            id=uuid4(),
            tour_id=tour_id,
            revision=len(self.get_plans(tour_id)) + 1,
            feedback=feedback,
            payload=payload,
            new_agent_messages=new_agent_messages,
            created_at=now(),
        )
        self.plans[plan.id] = plan
        self.set_status(tour_id, TourStatus.AWAITING_REVIEW)
        return plan

    def begin_production(self, tour_id: UUID, plan_id: UUID) -> bool:
        tour = self.tours[tour_id]
        if tour.status == TourStatus.READY and tour.approved_plan_id == plan_id:
            return False
        self.tours[tour_id] = tour.model_copy(update={"approved_plan_id": plan_id})
        self.set_status(tour_id, TourStatus.WRITING_CHAPTERS)
        return True

    def get_output(self, tour_id: UUID, plan_id: UUID | None = None) -> TourOutput | None:
        outputs = [
            output
            for output in self.outputs.values()
            if output.tour_id == tour_id
            and (plan_id is None or output.plan_id == plan_id)
        ]
        return outputs[-1] if outputs else None

    def save_output(
        self,
        tour_id: UUID,
        plan_id: UUID,
        *,
        title: str,
        payload: TourOutputPayload,
        status: TourStatus,
    ) -> Tour:
        key = (tour_id, plan_id)
        existing = self.outputs.get(key)
        self.outputs[key] = TourOutput(
            id=existing.id if existing else uuid4(),
            tour_id=tour_id,
            plan_id=plan_id,
            payload=payload,
            created_at=existing.created_at if existing else now(),
        )
        self.tours[tour_id] = self.tours[tour_id].model_copy(update={"title": title})
        return self.set_status(tour_id, status)


class TourApiTest(unittest.TestCase):
    def setUp(self) -> None:
        self.runner = FakePipeline()
        self.repository = MemoryTourRepository()
        self.artifacts = MemoryArtifactStore()
        app = create_app(
            repository=self.repository,
            artifact_store=self.artifacts,
            owner_id=OWNER_ID,
            runner=self.runner,
            geocoder_factory=UnusedGeocoder,
            tts_provider_factory=UnusedTTSProvider,
        )
        self.client_context = TestClient(app)
        self.client = self.client_context.__enter__()

    def tearDown(self) -> None:
        self.client_context.__exit__(None, None, None)

    def test_plan_approval_and_audio_flow(self) -> None:
        planned = self.client.post(
            "/tours",
            json={
                "location": "Test City",
                "request": "A short literary history walk",
                "min_stops": 2,
                "max_stops": 7,
                "max_checkpoint_distance_km": 12.5,
                "voice": "Kore",
            },
        ).json()

        self.assertEqual(planned["status"], "awaiting_review")
        self.assertEqual(planned["plan"]["revision"], 1)
        self.assertEqual(self.runner.research_calls[0]["max_stops"], 7)
        checkpoints = planned["plan"]["payload"]["checkpoints"]
        self.assertEqual([item["title"] for item in checkpoints], ["Old Library", "Clock Tower"])

        tour_id = planned["id"]
        plan_id = planned["plan"]["id"]
        response = self.client.post(
            f"/tours/{tour_id}/approve", json={"plan_id": plan_id}
        )
        self.assertEqual(response.status_code, 200)
        produced = response.json()
        self.assertEqual(produced["status"], "ready")
        self.assertEqual(produced["title"], "Books and Bells")
        self.assertEqual(len(produced["output"]["chapters"]), 2)
        self.assertEqual(len(self.artifacts.files), 2)

        audio_response = self.client.get(
            f"/tours/{tour_id}/chapters/1/audio", follow_redirects=False
        )
        self.assertEqual(audio_response.status_code, 307)
        self.assertTrue(audio_response.headers["location"].startswith("https://storage.test/"))

        repeat = self.client.post(
            f"/tours/{tour_id}/approve", json={"plan_id": plan_id}
        )
        self.assertEqual(repeat.status_code, 200)
        self.assertEqual(self.runner.write_calls, 1)
        self.assertEqual(self.runner.narrate_calls, 1)

    def test_rejects_an_inverted_stop_range(self) -> None:
        response = self.client.post(
            "/tours",
            json={
                "location": "Test City",
                "request": "A history walk",
                "min_stops": 8,
                "max_stops": 3,
            },
        )
        self.assertEqual(response.status_code, 422)
        self.assertEqual(self.runner.research_calls, [])

    def test_rejects_approval_for_a_different_plan(self) -> None:
        planned = self.client.post(
            "/tours", json={"location": "Test City", "request": "A history walk"}
        ).json()
        response = self.client.post(
            f"/tours/{planned['id']}/approve", json={"plan_id": str(uuid4())}
        )
        self.assertEqual(response.status_code, 409)
        self.assertEqual(
            response.json()["detail"],
            "The approved plan is not the current tour plan",
        )

    def test_feedback_stores_only_new_agent_messages(self) -> None:
        tour = self.client.post(
            "/tours", json={"location": "Test City", "request": "A history walk"}
        ).json()

        for feedback in ["Add industrial history", "Make the ending dramatic"]:
            response = self.client.post(
                f"/tours/{tour['id']}/feedback",
                json={"plan_id": tour["plan"]["id"], "feedback": feedback},
            )
            self.assertEqual(response.status_code, 200)
            tour = response.json()

        self.assertEqual(len(self.runner.research_calls[1]["message_history"]), 1)
        self.assertEqual(len(self.runner.research_calls[2]["message_history"]), 2)
        plans = self.repository.get_plans(UUID(tour["id"]))
        self.assertEqual([len(plan.new_agent_messages) for plan in plans], [1, 1, 1])

    def test_feedback_rejects_a_stale_plan(self) -> None:
        first = self.client.post(
            "/tours", json={"location": "Test City", "request": "A history walk"}
        ).json()
        revised = self.client.post(
            f"/tours/{first['id']}/feedback",
            json={"plan_id": first["plan"]["id"], "feedback": "Change it"},
        ).json()
        stale = self.client.post(
            f"/tours/{first['id']}/feedback",
            json={"plan_id": first["plan"]["id"], "feedback": "Again"},
        )
        self.assertEqual(revised["plan"]["revision"], 2)
        self.assertEqual(stale.status_code, 409)

    def test_feedback_is_limited_to_three_rounds(self) -> None:
        tour = self.client.post(
            "/tours", json={"location": "Test City", "request": "A history walk"}
        ).json()
        for number in range(3):
            tour = self.client.post(
                f"/tours/{tour['id']}/feedback",
                json={
                    "plan_id": tour["plan"]["id"],
                    "feedback": f"Round {number}",
                },
            ).json()
        response = self.client.post(
            f"/tours/{tour['id']}/feedback",
            json={"plan_id": tour["plan"]["id"], "feedback": "One more"},
        )
        self.assertEqual(response.status_code, 409)

    def test_cors_allows_the_local_pwa(self) -> None:
        response = self.client.options(
            "/tours",
            headers={
                "Origin": "http://127.0.0.1:5173",
                "Access-Control-Request-Method": "GET",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.headers["access-control-allow-origin"],
            "http://127.0.0.1:5173",
        )


class AuthenticationTest(unittest.TestCase):
    def test_tour_endpoints_require_a_supabase_token(self) -> None:
        app = create_app(
            repository=MemoryTourRepository(), artifact_store=MemoryArtifactStore()
        )
        with TestClient(app) as client:
            response = client.get("/tours")
        self.assertEqual(response.status_code, 401)


if __name__ == "__main__":
    unittest.main()
