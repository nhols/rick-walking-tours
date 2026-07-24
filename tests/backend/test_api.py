import unittest
from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from tour_gen.agents.chapter_writer import Chapter, ChapterWriterOutput, TTSStyle
from tour_gen.agents.checkpoint_researcher import (
    CheckpointProposal,
    CheckpointResearchOutput,
)
from tour_gen.agents.route_planner import OrderedCheckpoint, RoutePlanOutput
from tour_gen.backend.app import create_app
from tour_gen.backend.models import (
    ChapterStatus,
    Tour,
    TourChapter,
    TourCheckpoint,
    TourCreate,
    TourPlan,
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
        self.route_feedback: list[str | None] = []

    async def research_checkpoints(
        self,
        *,
        user_request,
        location,
        geocoder,
        feedback=None,
        message_history=None,
    ):
        history = list(message_history or [])
        self.research_calls.append(
            {
                "feedback": feedback,
                "message_history": history,
            }
        )
        return CheckpointResearchRun(
            output=CheckpointResearchOutput(
                proposals=[
                    CheckpointProposal(
                        title="Old Library",
                        brief_description="The story begins among historic books.",
                        distance_tool_place_name="Old Library, Test City",
                    ),
                    CheckpointProposal(
                        title="Clock Tower",
                        brief_description="A landmark that closes the story.",
                        distance_tool_place_name="Clock Tower, Test City",
                    ),
                ]
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
            agent_messages=[
                *history,
                {
                    "prompt": feedback or user_request,
                    "round": len(history) + 1,
                },
            ],
        )

    async def plan_route(self, checkpoint_research, *, feedback=None):
        self.route_feedback.append(feedback)
        return RoutePlanOutput(
            ordered_checkpoints=[
                OrderedCheckpoint(
                    title="Old Library",
                    reasoning="Introduces the tour's theme.",
                ),
                OrderedCheckpoint(
                    title="Clock Tower",
                    reasoning="Provides a natural finale.",
                ),
            ],
            narrative_arc="From the written past to the city's public clock.",
        )

    async def write_chapters(
        self,
        *,
        route_plan,
        checkpoint_research,
        location,
        voice_style=None,
    ):
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
                for item in route_plan.ordered_checkpoints
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
        self.checkpoints: dict[UUID, TourCheckpoint] = {}
        self.chapters: dict[UUID, TourChapter] = {}

    def create_tour(self, owner_id: UUID, data: TourCreate) -> Tour:
        timestamp = now()
        tour = Tour(
            id=uuid4(),
            owner_id=owner_id,
            **data.model_dump(),
            status=TourStatus.RESEARCHING,
            current_plan_revision=0,
            progress_message="Researching checkpoints",
            created_at=timestamp,
            updated_at=timestamp,
        )
        self.tours[tour.id] = tour
        return tour

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

    def update_tour(self, tour_id: UUID, values: Mapping[str, Any]) -> Tour:
        tour = self.tours[tour_id]
        updated = Tour.model_validate(
            {**tour.model_dump(), **dict(values), "updated_at": now()}
        )
        self.tours[tour_id] = updated
        return updated

    def get_plan(self, tour_id: UUID, plan_id: UUID | None = None) -> TourPlan | None:
        matches = [
            plan
            for plan in self.plans.values()
            if plan.tour_id == tour_id and (plan_id is None or plan.id == plan_id)
        ]
        return max(matches, key=lambda item: item.revision) if matches else None

    def get_checkpoints(self, tour_id: UUID, plan_id: UUID) -> list[TourCheckpoint]:
        return sorted(
            [
                item
                for item in self.checkpoints.values()
                if item.tour_id == tour_id and item.plan_id == plan_id
            ],
            key=lambda item: item.position,
        )

    def get_chapters(self, tour_id: UUID, plan_id: UUID | None = None) -> list[TourChapter]:
        return sorted(
            [
                item
                for item in self.chapters.values()
                if item.tour_id == tour_id
                and (plan_id is None or item.plan_id == plan_id)
            ],
            key=lambda item: item.position,
        )

    def persist_plan(
        self,
        tour_id: UUID,
        *,
        checkpoint_research,
        route_plan,
        checkpoints,
        parent_plan_id,
        feedback,
        checkpoint_agent_messages,
    ) -> TourPlan:
        tour = self.tours[tour_id]
        current_plan = self.get_plan(tour_id)
        if current_plan is None and parent_plan_id is not None:
            raise ValueError("The initial plan cannot have a parent")
        if current_plan is not None and parent_plan_id != current_plan.id:
            raise ValueError("Feedback must target the current tour plan")
        timestamp = now()
        plan = TourPlan(
            id=uuid4(),
            tour_id=tour_id,
            revision=tour.current_plan_revision + 1,
            checkpoint_research=checkpoint_research,
            route_plan=route_plan,
            parent_plan_id=parent_plan_id,
            feedback=feedback,
            checkpoint_agent_messages=checkpoint_agent_messages,
            created_at=timestamp,
        )
        self.plans[plan.id] = plan
        for item in checkpoints:
            checkpoint = TourCheckpoint(
                id=uuid4(), tour_id=tour_id, plan_id=plan.id, **item
            )
            self.checkpoints[checkpoint.id] = checkpoint
        self.update_tour(
            tour_id,
            {
                "status": TourStatus.AWAITING_REVIEW,
                "narrative_arc": route_plan["narrative_arc"],
                "current_plan_revision": plan.revision,
                "progress_message": "Plan ready for review",
                "progress_current": len(checkpoints),
                "progress_total": len(checkpoints),
            },
        )
        return plan

    def begin_production(self, tour_id: UUID, plan_id: UUID) -> bool:
        self.update_tour(
            tour_id,
            {
                "status": TourStatus.WRITING_CHAPTERS,
                "approved_plan_id": plan_id,
                "approved_at": now(),
                "progress_message": "Writing chapters",
            },
        )
        return True

    def persist_written_chapters(
        self,
        tour_id: UUID,
        plan_id: UUID,
        *,
        tour_title,
        tts_style,
        chapters,
    ) -> list[TourChapter]:
        timestamp = now()
        for item in chapters:
            chapter = TourChapter(
                id=uuid4(),
                tour_id=tour_id,
                plan_id=plan_id,
                status=ChapterStatus.WRITTEN,
                created_at=timestamp,
                updated_at=timestamp,
                **item,
            )
            self.chapters[chapter.id] = chapter
        self.update_tour(tour_id, {"title": tour_title, "tts_style": tts_style})
        return self.get_chapters(tour_id, plan_id)

    def finalize_audio(self, tour_id: UUID, audio: list[dict[str, Any]]) -> Tour:
        for item in audio:
            chapter_id = UUID(item["chapter_id"])
            chapter = self.chapters[chapter_id]
            self.chapters[chapter_id] = TourChapter.model_validate(
                {
                    **chapter.model_dump(),
                    **item,
                    "id": chapter_id,
                    "status": ChapterStatus.READY,
                    "updated_at": now(),
                }
            )
        return self.update_tour(
            tour_id,
            {
                "status": TourStatus.READY,
                "progress_message": "Tour ready",
                "progress_current": len(audio),
                "progress_total": len(audio),
            },
        )


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
        create_response = self.client.post(
            "/tours",
            json={
                "location": "Test City",
                "request": "A short literary history walk",
                "voice": "Kore",
            },
        )

        self.assertEqual(create_response.status_code, 201)
        planned = create_response.json()
        self.assertEqual(planned["status"], "awaiting_review")
        self.assertEqual(planned["plan"]["revision"], 1)
        self.assertEqual(
            [item["title"] for item in planned["plan"]["checkpoints"]],
            ["Old Library", "Clock Tower"],
        )

        tour_id = planned["id"]
        plan_id = planned["plan"]["id"]
        approval_response = self.client.post(
            f"/tours/{tour_id}/approve",
            json={"plan_id": plan_id},
        )

        self.assertEqual(approval_response.status_code, 200)
        produced = approval_response.json()
        self.assertEqual(produced["status"], "ready")
        self.assertEqual(produced["title"], "Books and Bells")
        self.assertEqual(len(produced["chapters"]), 2)
        self.assertEqual(produced["chapters"][0]["status"], "ready")
        self.assertEqual(len(self.artifacts.files), 2)

        audio_response = self.client.get(
            produced["chapters"][0]["audio_url"],
            follow_redirects=False,
        )
        self.assertEqual(audio_response.status_code, 307)
        self.assertTrue(audio_response.headers["location"].startswith("https://storage.test/"))

        detail_response = self.client.get(f"/tours/{tour_id}")
        self.assertEqual(detail_response.status_code, 200)
        self.assertEqual(detail_response.json()["status"], "ready")
        self.assertEqual(len(self.client.get("/tours").json()), 1)

        repeat_response = self.client.post(
            f"/tours/{tour_id}/approve",
            json={"plan_id": plan_id},
        )
        self.assertEqual(repeat_response.status_code, 200)
        self.assertEqual(self.runner.write_calls, 1)
        self.assertEqual(self.runner.narrate_calls, 1)

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

    def test_rejects_approval_for_a_different_plan(self) -> None:
        planned = self.client.post(
            "/tours",
            json={"location": "Test City", "request": "A history walk"},
        ).json()

        response = self.client.post(
            f"/tours/{planned['id']}/approve",
            json={"plan_id": str(uuid4())},
        )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(
            response.json()["detail"],
            "The approved plan is not the current tour plan",
        )
        detail = self.client.get(f"/tours/{planned['id']}").json()
        self.assertEqual(detail["status"], "awaiting_review")

    def test_feedback_creates_revisions_with_cumulative_research_history(self) -> None:
        first = self.client.post(
            "/tours",
            json={"location": "Test City", "request": "A history walk"},
        ).json()

        second_response = self.client.post(
            f"/tours/{first['id']}/feedback",
            json={
                "plan_id": first["plan"]["id"],
                "feedback": "Add more industrial history",
            },
        )
        self.assertEqual(second_response.status_code, 200)
        second = second_response.json()
        self.assertEqual(second["plan"]["revision"], 2)
        self.assertEqual(second["plan"]["parent_plan_id"], first["plan"]["id"])
        self.assertEqual(second["plan"]["feedback"], "Add more industrial history")
        self.assertEqual(len(self.runner.research_calls[1]["message_history"]), 1)
        self.assertEqual(self.runner.route_feedback[1], "Add more industrial history")

        third_response = self.client.post(
            f"/tours/{first['id']}/feedback",
            json={
                "plan_id": second["plan"]["id"],
                "feedback": "Make the ending more dramatic",
            },
        )
        self.assertEqual(third_response.status_code, 200)
        third = third_response.json()
        self.assertEqual(third["plan"]["revision"], 3)
        self.assertEqual(third["plan"]["parent_plan_id"], second["plan"]["id"])
        self.assertEqual(len(self.runner.research_calls[2]["message_history"]), 2)
        self.assertEqual(self.runner.route_feedback[2], "Make the ending more dramatic")

        original = self.repository.get_plan(
            UUID(first["id"]),
            UUID(first["plan"]["id"]),
        )
        if original is None:
            self.fail("Original plan revision was not persisted")
        self.assertIsNone(original.feedback)

    def test_feedback_rejects_a_stale_plan(self) -> None:
        first = self.client.post(
            "/tours",
            json={"location": "Test City", "request": "A history walk"},
        ).json()
        revised = self.client.post(
            f"/tours/{first['id']}/feedback",
            json={"plan_id": first["plan"]["id"], "feedback": "Change it"},
        )
        self.assertEqual(revised.status_code, 200)

        stale = self.client.post(
            f"/tours/{first['id']}/feedback",
            json={"plan_id": first["plan"]["id"], "feedback": "Change it again"},
        )

        self.assertEqual(stale.status_code, 409)
        self.assertEqual(
            stale.json()["detail"],
            "Feedback must target the current tour plan",
        )
        self.assertEqual(len(self.runner.research_calls), 2)

    def test_feedback_is_limited_to_three_rounds(self) -> None:
        tour = self.client.post(
            "/tours",
            json={"location": "Test City", "request": "A history walk"},
        ).json()

        for round_number in range(1, 4):
            response = self.client.post(
                f"/tours/{tour['id']}/feedback",
                json={
                    "plan_id": tour["plan"]["id"],
                    "feedback": f"Feedback round {round_number}",
                },
            )
            self.assertEqual(response.status_code, 200)
            tour = response.json()

        response = self.client.post(
            f"/tours/{tour['id']}/feedback",
            json={"plan_id": tour["plan"]["id"], "feedback": "One more change"},
        )
        self.assertEqual(response.status_code, 409)
        self.assertEqual(
            response.json()["detail"],
            "A tour can have at most 3 feedback rounds",
        )


class AuthenticationTest(unittest.TestCase):
    def test_tour_endpoints_require_a_supabase_token(self) -> None:
        app = create_app(
            repository=MemoryTourRepository(),
            artifact_store=MemoryArtifactStore(),
        )

        with TestClient(app) as client:
            response = client.get("/tours")

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["detail"], "A Supabase access token is required")


if __name__ == "__main__":
    unittest.main()
