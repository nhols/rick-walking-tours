from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, Field

from tour_gen.backend.assistant import TourAssistantInput


class PlanPayload(BaseModel):
    kind: Literal["plan"]


class RevisionPayload(BaseModel):
    kind: Literal["revise"]
    plan_id: UUID
    feedback: str


class ProductionPayload(BaseModel):
    kind: Literal["produce"]
    plan_id: UUID


type JobPayload = Annotated[
    PlanPayload | RevisionPayload | ProductionPayload,
    Field(discriminator="kind"),
]


class TourJob(BaseModel):
    tour_id: UUID
    payload: JobPayload


class TourAssistantEvent(BaseModel):
    action: Literal["ask_tour"]
    tour_id: UUID
    user_id: UUID
    input: TourAssistantInput
