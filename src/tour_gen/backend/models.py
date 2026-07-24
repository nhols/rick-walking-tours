from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class TourStatus(str, Enum):
    RESEARCHING = "researching"
    PLANNING_ROUTE = "planning_route"
    AWAITING_REVIEW = "awaiting_review"
    WRITING_CHAPTERS = "writing_chapters"
    GENERATING_AUDIO = "generating_audio"
    READY = "ready"
    FAILED = "failed"


class ChapterStatus(str, Enum):
    WRITTEN = "written"
    READY = "ready"


class Tour(BaseModel):
    id: UUID
    owner_id: UUID
    location: str
    request: str
    status: TourStatus
    title: str | None = None
    narrative_arc: str | None = None
    voice: str
    voice_style: str | None = None
    tts_model: str | None = None
    audio_format: str
    tts_style: dict[str, Any] | None = None
    current_plan_revision: int
    approved_plan_id: UUID | None = None
    progress_message: str | None = None
    progress_current: int | None = None
    progress_total: int | None = None
    error_message: str | None = None
    approved_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class TourPlan(BaseModel):
    id: UUID
    tour_id: UUID
    revision: int
    checkpoint_research: dict[str, Any]
    route_plan: dict[str, Any]
    parent_plan_id: UUID | None = None
    feedback: str | None = None
    checkpoint_agent_messages: list[dict[str, Any]] = Field(default_factory=list)
    created_at: datetime


class TourCheckpoint(BaseModel):
    id: UUID
    tour_id: UUID
    plan_id: UUID
    position: int
    title: str
    description: str
    route_reasoning: str
    distance_tool_place_name: str
    lat: float
    lon: float
    formatted_address: str | None = None


class TourChapter(BaseModel):
    id: UUID
    tour_id: UUID
    plan_id: UUID
    checkpoint_id: UUID
    position: int
    title: str
    narration: str
    status: ChapterStatus
    audio_path: str | None = None
    media_type: str | None = None
    audio_format: str | None = None
    byte_count: int | None = None
    voice: str | None = None
    model: str | None = None
    duration_seconds: float | None = None
    created_at: datetime
    updated_at: datetime


class TourCreate(BaseModel):
    location: str = Field(min_length=1, max_length=240)
    request: str = Field(min_length=1, max_length=4_000)
    voice: str = Field(default="Kore", min_length=1, max_length=120)
    voice_style: str | None = Field(default=None, max_length=2_000)
    tts_model: str | None = Field(default=None, max_length=240)
    audio_format: str = Field(default="wav", min_length=1, max_length=20)


class TourApproval(BaseModel):
    plan_id: UUID


class TourFeedback(BaseModel):
    plan_id: UUID
    feedback: str = Field(min_length=1, max_length=2_000)

    @field_validator("feedback")
    @classmethod
    def feedback_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Feedback must not be blank")
        return value


class CheckpointRead(BaseModel):
    id: UUID
    position: int
    title: str
    description: str
    route_reasoning: str
    distance_tool_place_name: str
    lat: float
    lon: float
    formatted_address: str | None


class PlanRead(BaseModel):
    id: UUID
    revision: int
    parent_plan_id: UUID | None
    feedback: str | None
    narrative_arc: str
    checkpoints: list[CheckpointRead]
    created_at: datetime


class ChapterRead(BaseModel):
    id: UUID
    position: int
    title: str
    narration: str
    status: ChapterStatus
    audio_url: str | None
    media_type: str | None
    audio_format: str | None
    byte_count: int | None
    voice: str | None
    model: str | None
    duration_seconds: float | None


class TourRead(BaseModel):
    id: UUID
    owner_id: UUID
    location: str
    request: str
    status: TourStatus
    title: str | None
    voice: str
    voice_style: str | None
    progress_message: str | None
    progress_current: int | None
    progress_total: int | None
    error_message: str | None
    approved_plan_id: UUID | None
    plan: PlanRead | None
    chapters: list[ChapterRead]
    created_at: datetime
    updated_at: datetime


class TourSummary(BaseModel):
    id: UUID
    location: str
    request: str
    status: TourStatus
    title: str | None
    progress_message: str | None
    created_at: datetime
    updated_at: datetime
