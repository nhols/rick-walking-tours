import os
from collections.abc import Mapping
from enum import Enum
from typing import Any, Protocol
from uuid import UUID

from pydantic import BaseModel
from supabase import Client, create_client

from tour_gen.backend.models import (
    ChapterRead,
    CheckpointRead,
    PlanRead,
    Tour,
    TourChapter,
    TourCheckpoint,
    TourCreate,
    TourPlan,
    TourRead,
    TourStatus,
    TourSummary,
)


class TourRepository(Protocol):
    def create_tour(self, owner_id: UUID, data: TourCreate) -> Tour: ...

    def get_tour(self, tour_id: UUID, owner_id: UUID | None = None) -> Tour | None: ...

    def list_tours(self, owner_id: UUID) -> list[TourSummary]: ...

    def update_tour(self, tour_id: UUID, values: Mapping[str, Any]) -> Tour: ...

    def get_plan(self, tour_id: UUID, plan_id: UUID | None = None) -> TourPlan | None: ...

    def get_checkpoints(self, tour_id: UUID, plan_id: UUID) -> list[TourCheckpoint]: ...

    def get_chapters(self, tour_id: UUID, plan_id: UUID | None = None) -> list[TourChapter]: ...

    def persist_plan(
        self,
        tour_id: UUID,
        *,
        checkpoint_research: dict[str, Any],
        route_plan: dict[str, Any],
        checkpoints: list[dict[str, Any]],
        parent_plan_id: UUID | None,
        feedback: str | None,
        checkpoint_agent_messages: list[dict[str, Any]],
    ) -> TourPlan: ...

    def begin_production(self, tour_id: UUID, plan_id: UUID) -> bool: ...

    def persist_written_chapters(
        self,
        tour_id: UUID,
        plan_id: UUID,
        *,
        tour_title: str,
        tts_style: dict[str, Any],
        chapters: list[dict[str, Any]],
    ) -> list[TourChapter]: ...

    def finalize_audio(
        self,
        tour_id: UUID,
        audio: list[dict[str, Any]],
    ) -> Tour: ...


class InsufficientCreditsError(Exception):
    pass


class SupabaseTourRepository:
    def __init__(self, client: Client) -> None:
        self.client = client

    @classmethod
    def from_env(cls) -> "SupabaseTourRepository":
        return cls(create_supabase_client_from_env())

    def create_tour(self, owner_id: UUID, data: TourCreate) -> Tour:
        payload = {
            "owner_id": str(owner_id),
            **data.model_dump(mode="json"),
            "status": TourStatus.RESEARCHING.value,
            "progress_message": "Researching checkpoints",
        }
        response = self.client.table("tours").insert(payload).execute()
        return _one(Tour, response.data, "create tour")

    def get_tour(self, tour_id: UUID, owner_id: UUID | None = None) -> Tour | None:
        query = self.client.table("tours").select("*").eq("id", str(tour_id))
        if owner_id is not None:
            query = query.eq("owner_id", str(owner_id))
        response = query.limit(1).execute()
        return _optional_one(Tour, response.data)

    def list_tours(self, owner_id: UUID) -> list[TourSummary]:
        response = (
            self.client.table("tours")
            .select("*")
            .eq("owner_id", str(owner_id))
            .order("created_at", desc=True)
            .execute()
        )
        return [TourSummary.model_validate(item) for item in response.data]

    def update_tour(self, tour_id: UUID, values: Mapping[str, Any]) -> Tour:
        response = (
            self.client.table("tours")
            .update(_jsonable(values))
            .eq("id", str(tour_id))
            .execute()
        )
        return _one(Tour, response.data, "update tour")

    def get_plan(self, tour_id: UUID, plan_id: UUID | None = None) -> TourPlan | None:
        query = (
            self.client.table("tour_plan_revisions")
            .select("*")
            .eq("tour_id", str(tour_id))
        )
        if plan_id is not None:
            query = query.eq("id", str(plan_id))
        response = query.order("revision", desc=True).limit(1).execute()
        return _optional_one(TourPlan, response.data)

    def get_checkpoints(self, tour_id: UUID, plan_id: UUID) -> list[TourCheckpoint]:
        response = (
            self.client.table("tour_checkpoints")
            .select("*")
            .eq("tour_id", str(tour_id))
            .eq("plan_id", str(plan_id))
            .order("position")
            .execute()
        )
        return [TourCheckpoint.model_validate(item) for item in response.data]

    def get_chapters(self, tour_id: UUID, plan_id: UUID | None = None) -> list[TourChapter]:
        query = (
            self.client.table("tour_chapters")
            .select("*")
            .eq("tour_id", str(tour_id))
        )
        if plan_id is not None:
            query = query.eq("plan_id", str(plan_id))
        response = query.order("position").execute()
        return [TourChapter.model_validate(item) for item in response.data]

    def persist_plan(
        self,
        tour_id: UUID,
        *,
        checkpoint_research: dict[str, Any],
        route_plan: dict[str, Any],
        checkpoints: list[dict[str, Any]],
        parent_plan_id: UUID | None,
        feedback: str | None,
        checkpoint_agent_messages: list[dict[str, Any]],
    ) -> TourPlan:
        response = self.client.rpc(
            "persist_tour_plan",
            {
                "p_tour_id": str(tour_id),
                "p_checkpoint_research": checkpoint_research,
                "p_route_plan": route_plan,
                "p_checkpoints": checkpoints,
                "p_parent_plan_id": str(parent_plan_id) if parent_plan_id else None,
                "p_feedback": feedback,
                "p_checkpoint_agent_messages": checkpoint_agent_messages,
            },
        ).execute()
        plan_id = UUID(str(response.data))
        plan = self.get_plan(tour_id, plan_id)
        if plan is None:
            raise RuntimeError("Plan was persisted but could not be read")
        return plan

    def begin_production(self, tour_id: UUID, plan_id: UUID) -> bool:
        try:
            response = self.client.rpc(
                "begin_tour_production",
                {"p_tour_id": str(tour_id), "p_plan_id": str(plan_id)},
            ).execute()
        except Exception as error:
            if "Insufficient credits" in str(error):
                raise InsufficientCreditsError from error
            raise
        return bool(response.data)

    def persist_written_chapters(
        self,
        tour_id: UUID,
        plan_id: UUID,
        *,
        tour_title: str,
        tts_style: dict[str, Any],
        chapters: list[dict[str, Any]],
    ) -> list[TourChapter]:
        self.client.rpc(
            "persist_written_chapters",
            {
                "p_tour_id": str(tour_id),
                "p_plan_id": str(plan_id),
                "p_tour_title": tour_title,
                "p_tts_style": tts_style,
                "p_chapters": chapters,
            },
        ).execute()
        return self.get_chapters(tour_id, plan_id)

    def finalize_audio(
        self,
        tour_id: UUID,
        audio: list[dict[str, Any]],
    ) -> Tour:
        self.client.rpc(
            "finalize_tour_audio",
            {"p_tour_id": str(tour_id), "p_audio": audio},
        ).execute()
        tour = self.get_tour(tour_id)
        if tour is None:
            raise RuntimeError("Tour was finalized but could not be read")
        return tour


def create_supabase_client_from_env() -> Client:
    url = os.environ.get("SUPABASE_URL") or os.environ.get("API_URL")
    service_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get(
        "SERVICE_ROLE_KEY"
    )
    if not url or not service_key:
        raise RuntimeError(
            "SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set. "
            "For local development, run `npm run dev`."
        )
    return create_client(url, service_key)


def tour_to_read(repository: TourRepository, tour: Tour) -> TourRead:
    plan_record = repository.get_plan(tour.id)
    checkpoints = (
        repository.get_checkpoints(tour.id, plan_record.id)
        if plan_record is not None
        else []
    )
    chapters = repository.get_chapters(tour.id, tour.approved_plan_id)

    plan = None
    if plan_record is not None:
        plan = PlanRead(
            id=plan_record.id,
            revision=plan_record.revision,
            parent_plan_id=plan_record.parent_plan_id,
            feedback=plan_record.feedback,
            narrative_arc=str(plan_record.route_plan["narrative_arc"]),
            checkpoints=[
                CheckpointRead.model_validate(item.model_dump()) for item in checkpoints
            ],
            created_at=plan_record.created_at,
        )

    return TourRead(
        id=tour.id,
        owner_id=tour.owner_id,
        location=tour.location,
        request=tour.request,
        status=tour.status,
        title=tour.title,
        voice=tour.voice,
        voice_style=tour.voice_style,
        progress_message=tour.progress_message,
        progress_current=tour.progress_current,
        progress_total=tour.progress_total,
        error_message=tour.error_message,
        approved_plan_id=tour.approved_plan_id,
        plan=plan,
        chapters=[
            ChapterRead(
                id=chapter.id,
                position=chapter.position,
                title=chapter.title,
                narration=chapter.narration,
                status=chapter.status,
                audio_url=(
                    f"/tours/{tour.id}/chapters/{chapter.position}/audio"
                    if chapter.audio_path
                    else None
                ),
                media_type=chapter.media_type,
                audio_format=chapter.audio_format,
                byte_count=chapter.byte_count,
                voice=chapter.voice,
                model=chapter.model,
                duration_seconds=chapter.duration_seconds,
            )
            for chapter in chapters
        ],
        created_at=tour.created_at,
        updated_at=tour.updated_at,
    )


def _one[T: BaseModel](model: type[T], data: list[Any], operation: str) -> T:
    if len(data) != 1:
        raise RuntimeError(f"Expected one row after {operation}, received {len(data)}")
    return model.model_validate(data[0])


def _optional_one[T: BaseModel](model: type[T], data: list[Any]) -> T | None:
    if not data:
        return None
    return model.model_validate(data[0])


def _jsonable(values: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: value.value if isinstance(value, Enum) else str(value) if isinstance(value, UUID) else value
        for key, value in values.items()
    }
