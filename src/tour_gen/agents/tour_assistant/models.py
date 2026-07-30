from dataclasses import dataclass, field
from typing import Protocol
from uuid import UUID

from pydantic import BaseModel

from tour_gen.backend.models import Tour, TourChapter, TourOutputPayload, TourPlan


class TourAssistantContext(BaseModel):
    tour: Tour
    approved_plan: TourPlan
    output: TourOutputPayload
    selected_chapter: TourChapter


class TourAssistantContextLoader(Protocol):
    def load(
        self,
        tour_id: UUID,
        selected_chapter_id: UUID,
    ) -> TourAssistantContext: ...


@dataclass
class TourAssistantDeps:
    tour_id: UUID
    selected_chapter_id: UUID
    chapter_playback_seconds: float
    context_loader: TourAssistantContextLoader
    _context: TourAssistantContext | None = field(
        default=None,
        init=False,
        repr=False,
    )

    def __post_init__(self) -> None:
        if self.chapter_playback_seconds < 0:
            raise ValueError("chapter_playback_seconds must not be negative")

    def load_context(self) -> TourAssistantContext:
        if self._context is None:
            self._context = self.context_loader.load(
                self.tour_id,
                self.selected_chapter_id,
            )
        return self._context
