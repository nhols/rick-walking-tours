from typing import Any
from uuid import UUID

from pydantic import BaseModel
from supabase import Client

from tour_gen.backend.models import (
    Tour,
    TourOutputPayload,
    TourPlan,
    TourStatus,
)
from tour_gen.backend.ports import GeneratedPlan


class _MessageRow(BaseModel):
    new_agent_messages: list[dict[str, Any]]


class SupabaseTourStore:
    def __init__(self, client: Client) -> None:
        self.client = client

    def get_tour(self, tour_id: UUID) -> Tour | None:
        data = (
            self.client.table("tours")
            .select("*")
            .eq("id", str(tour_id))
            .limit(1)
            .execute()
            .data
        )
        return _first(Tour, data)

    def get_plan(self, tour_id: UUID) -> TourPlan | None:
        data = (
            self.client.table("tour_plan_revisions")
            .select("*")
            .eq("tour_id", str(tour_id))
            .order("revision", desc=True)
            .limit(1)
            .execute()
            .data
        )
        return _first(TourPlan, data)

    def get_agent_messages(self, tour_id: UUID) -> list[dict[str, Any]]:
        rows = (
            self.client.table("tour_plan_revisions")
            .select("new_agent_messages")
            .eq("tour_id", str(tour_id))
            .order("revision")
            .execute()
            .data
        )
        return [
            message
            for data in rows
            for message in _MessageRow.model_validate(data).new_agent_messages
        ]

    def save_plan(
        self,
        tour_id: UUID,
        *,
        feedback: str | None,
        generated: GeneratedPlan,
    ) -> None:
        self.client.rpc(
            "persist_tour_plan",
            {
                "p_tour_id": str(tour_id),
                "p_feedback": feedback,
                "p_payload": generated.payload.model_dump(mode="json"),
                "p_new_agent_messages": generated.new_messages,
            },
        ).execute()

    def save_output(
        self,
        tour_id: UUID,
        plan_id: UUID,
        *,
        title: str,
        output: TourOutputPayload,
        status: TourStatus,
    ) -> None:
        self.client.rpc(
            "save_tour_output",
            {
                "p_tour_id": str(tour_id),
                "p_plan_id": str(plan_id),
                "p_title": title,
                "p_payload": output.model_dump(mode="json"),
                "p_status": status.value,
            },
        ).execute()

    def set_status(
        self,
        tour_id: UUID,
        status: TourStatus,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.client.rpc(
            "record_tour_status",
            {
                "p_tour_id": str(tour_id),
                "p_status": status.value,
                "p_details": details,
            },
        ).execute()


def _first[T: BaseModel](model: type[T], rows: list[Any]) -> T | None:
    return model.model_validate(rows[0]) if rows else None
