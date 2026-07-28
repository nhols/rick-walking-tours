from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from tour_gen.geo.routes import WalkingRoute


class TourStatus(str, Enum):
    RESEARCHING = "researching"
    AWAITING_REVIEW = "awaiting_review"
    WRITING_CHAPTERS = "writing_chapters"
    GENERATING_AUDIO = "generating_audio"
    READY = "ready"
    FAILED = "failed"


class TourInput(BaseModel):
    location: str = Field(min_length=1, max_length=240)
    request: str = Field(min_length=1, max_length=4_000)
    min_stops: int = Field(default=2, ge=1, le=20)
    max_stops: int = Field(default=10, ge=1, le=20)
    max_checkpoint_distance_km: float = Field(default=10, gt=0, le=100)
    voice: str = Field(default="Kore", min_length=1, max_length=120)
    voice_style: str | None = Field(default=None, max_length=2_000)
    tts_model: str | None = Field(default=None, max_length=240)
    audio_format: str = Field(default="wav", min_length=1, max_length=20)

    @model_validator(mode="after")
    def validate_stop_range(self) -> "TourInput":
        if self.min_stops > self.max_stops:
            raise ValueError("min_stops must not exceed max_stops")
        return self


class Tour(BaseModel):
    id: UUID
    owner_id: UUID
    status: TourStatus
    title: str | None = None
    input: TourInput
    approved_plan_id: UUID | None = None
    created_at: datetime
    updated_at: datetime


class TourCheckpoint(BaseModel):
    id: UUID
    position: int = Field(gt=0)
    title: str
    description: str
    route_reasoning: str
    distance_tool_place_name: str
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    formatted_address: str | None = None


class TourPlanPayload(BaseModel):
    narrative_arc: str
    checkpoints: list[TourCheckpoint]
    route: WalkingRoute | None = None


class TourPlan(BaseModel):
    id: UUID
    tour_id: UUID
    revision: int
    feedback: str | None = None
    payload: TourPlanPayload
    new_agent_messages: list[dict[str, Any]] = Field(default_factory=list)
    created_at: datetime


class TourChapter(BaseModel):
    id: UUID
    checkpoint_id: UUID
    position: int = Field(gt=0)
    title: str
    narration: str
    audio_path: str | None = None
    duration_seconds: float | None = None


class TourOutputPayload(BaseModel):
    tts_style: dict[str, Any]
    chapters: list[TourChapter]
