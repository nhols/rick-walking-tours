from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel


class WorkerEvent(BaseModel):
    job_id: UUID
    tour_id: UUID
    kind: Literal["plan", "revise", "produce"]


class TourJob(BaseModel):
    id: UUID
    tour_id: UUID
    kind: Literal["plan", "revise", "produce"]
    input: dict[str, Any]
