from dataclasses import dataclass
from typing import Any, Protocol
from uuid import UUID

from tour_gen.backend.models import (
    Tour,
    TourInput,
    TourOutputPayload,
    TourPlan,
    TourPlanPayload,
    TourStatus,
)


@dataclass(frozen=True)
class GeneratedPlan:
    payload: TourPlanPayload
    new_messages: list[dict[str, Any]]


@dataclass(frozen=True)
class WrittenTour:
    title: str
    output: TourOutputPayload


class TourStore(Protocol):
    def get_tour(self, tour_id: UUID) -> Tour | None: ...
    def get_plan(self, tour_id: UUID) -> TourPlan | None: ...
    def get_agent_messages(self, tour_id: UUID) -> list[dict[str, Any]]: ...
    def save_plan(
        self,
        tour_id: UUID,
        *,
        feedback: str | None,
        generated: GeneratedPlan,
    ) -> None: ...
    def save_output(
        self,
        tour_id: UUID,
        plan_id: UUID,
        *,
        title: str,
        output: TourOutputPayload,
        status: TourStatus,
    ) -> None: ...
    def set_status(
        self,
        tour_id: UUID,
        status: TourStatus,
        details: dict[str, Any] | None = None,
    ) -> None: ...


class TourPlanner(Protocol):
    async def plan(
        self,
        input: TourInput,
        prompt: str,
        history: list[dict[str, Any]],
    ) -> GeneratedPlan: ...


class TourProducer(Protocol):
    async def write(self, input: TourInput, plan: TourPlanPayload) -> WrittenTour: ...
    async def narrate(
        self,
        owner_id: UUID,
        tour_id: UUID,
        input: TourInput,
        written: WrittenTour,
    ) -> TourOutputPayload: ...


class AudioStore(Protocol):
    def save(
        self,
        *,
        owner_id: UUID,
        tour_id: UUID,
        position: int,
        audio_format: str,
        media_type: str,
        audio: bytes,
    ) -> str: ...
