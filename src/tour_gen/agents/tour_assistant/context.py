from typing import Any
from uuid import UUID

from pydantic import BaseModel
from supabase import Client

from tour_gen.agents.tour_assistant.models import TourAssistantContext
from tour_gen.backend.models import Tour, TourOutputPayload, TourPlan


class _OutputRow(BaseModel):
    payload: TourOutputPayload


class SupabaseTourAssistantContextLoader:
    def __init__(self, client: Client) -> None:
        self.client = client

    def load(
        self,
        tour_id: UUID,
        selected_chapter_id: UUID,
    ) -> TourAssistantContext:
        tour = _first(
            Tour,
            self.client.table("tours")
            .select("*")
            .eq("id", str(tour_id))
            .limit(1)
            .execute()
            .data,
        )
        if tour is None:
            raise ValueError("Tour not found")
        if tour.approved_plan_id is None:
            raise ValueError("Tour has no approved plan")

        plan = _first(
            TourPlan,
            self.client.table("tour_plan_revisions")
            .select("*")
            .eq("tour_id", str(tour_id))
            .eq("id", str(tour.approved_plan_id))
            .limit(1)
            .execute()
            .data,
        )
        if plan is None:
            raise ValueError("Approved tour plan not found")

        output_row = _first(
            _OutputRow,
            self.client.table("tour_outputs")
            .select("payload")
            .eq("tour_id", str(tour_id))
            .eq("plan_id", str(tour.approved_plan_id))
            .limit(1)
            .execute()
            .data,
        )
        if output_row is None:
            raise ValueError("Tour output not found")

        selected_chapter = next(
            (
                chapter
                for chapter in output_row.payload.chapters
                if chapter.id == selected_chapter_id
            ),
            None,
        )
        if selected_chapter is None:
            raise ValueError("Selected chapter does not belong to this tour")

        return TourAssistantContext(
            tour=tour,
            approved_plan=plan,
            output=output_row.payload,
            selected_chapter=selected_chapter,
        )


def _first[T: BaseModel](model: type[T], rows: list[Any]) -> T | None:
    return model.model_validate(rows[0]) if rows else None
