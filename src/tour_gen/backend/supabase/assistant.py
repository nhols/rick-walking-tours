from typing import Any
from uuid import UUID

from pydantic import BaseModel
from supabase import Client

from tour_gen.backend.assistant import (
    TourAssistantInput,
    TourAssistantOutput,
    TourAssistantTurn,
)


class _TourAccess(BaseModel):
    owner_id: UUID
    is_public: bool
    status: str


class _ThreadRow(BaseModel):
    thread_id: UUID


class SupabaseTourAssistantStore:
    def __init__(self, client: Client) -> None:
        self.client = client

    def ensure_tour_access(self, tour_id: UUID, user_id: UUID) -> None:
        data = (
            self.client.table("tours")
            .select("owner_id,is_public,status")
            .eq("id", str(tour_id))
            .limit(1)
            .execute()
            .data
        )
        tour = _first(_TourAccess, data)
        if tour is None:
            raise ValueError("Tour not found")
        if tour.owner_id != user_id and not (
            tour.is_public and tour.status == "ready"
        ):
            raise ValueError("Tour not found")

    def get_turns(
        self,
        tour_id: UUID,
        user_id: UUID,
    ) -> list[TourAssistantTurn]:
        latest = (
            self.client.table("tour_assistant_turns")
            .select("thread_id")
            .eq("tour_id", str(tour_id))
            .eq("user_id", str(user_id))
            .order("created_at", desc=True)
            .limit(1)
            .execute()
            .data
        )
        latest_thread = _first(_ThreadRow, latest)
        if latest_thread is None:
            return []
        rows = (
            self.client.table("tour_assistant_turns")
            .select("*")
            .eq("tour_id", str(tour_id))
            .eq("user_id", str(user_id))
            .eq("thread_id", str(latest_thread.thread_id))
            .order("turn")
            .execute()
            .data
        )
        return [TourAssistantTurn.model_validate(row) for row in rows]

    def save_turn(
        self,
        *,
        tour_id: UUID,
        user_id: UUID,
        thread_id: UUID,
        turn: int,
        input: TourAssistantInput,
        output: TourAssistantOutput,
        new_messages: list[dict[str, Any]],
    ) -> None:
        self.client.table("tour_assistant_turns").insert(
            {
                "tour_id": str(tour_id),
                "user_id": str(user_id),
                "thread_id": str(thread_id),
                "turn": turn,
                "input": input.model_dump(mode="json"),
                "output": output.model_dump(mode="json"),
                "new_messages": new_messages,
            }
        ).execute()


def _first[T: BaseModel](model: type[T], rows: list[Any]) -> T | None:
    return model.model_validate(rows[0]) if rows else None
