from typing import Literal
from uuid import UUID

from pydantic import BaseModel


class WorkerEvent(BaseModel):
    run_id: UUID
    tour_id: UUID
    action: Literal["plan", "produce"]


class GenerationRun(BaseModel):
    id: UUID
    tour_id: UUID
    action: Literal["plan", "produce"]
    plan_id: UUID | None = None
    feedback: str | None = None
