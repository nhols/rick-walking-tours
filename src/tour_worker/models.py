from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, Field


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
