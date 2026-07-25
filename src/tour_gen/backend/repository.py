import os
from typing import Any, Protocol
from uuid import UUID

from pydantic import BaseModel
from supabase import Client, create_client

from tour_gen.backend.models import (
    PlanRead,
    Tour,
    TourInput,
    TourOutput,
    TourOutputPayload,
    TourPlan,
    TourPlanPayload,
    TourRead,
    TourStatus,
    TourSummary,
)


class TourRepository(Protocol):
    def create_tour(self, owner_id: UUID, data: TourInput) -> Tour: ...
    def get_tour(self, tour_id: UUID, owner_id: UUID | None = None) -> Tour | None: ...
    def list_tours(self, owner_id: UUID) -> list[TourSummary]: ...
    def set_status(
        self, tour_id: UUID, status: TourStatus, details: dict[str, Any] | None = None
    ) -> Tour: ...
    def get_plans(self, tour_id: UUID) -> list[TourPlan]: ...
    def get_plan(self, tour_id: UUID, plan_id: UUID | None = None) -> TourPlan | None: ...
    def get_agent_messages(self, tour_id: UUID) -> list[dict[str, Any]]: ...
    def persist_plan(
        self,
        tour_id: UUID,
        *,
        feedback: str | None,
        payload: TourPlanPayload,
        new_agent_messages: list[dict[str, Any]],
    ) -> TourPlan: ...
    def begin_production(self, tour_id: UUID, plan_id: UUID) -> bool: ...
    def get_output(self, tour_id: UUID, plan_id: UUID | None = None) -> TourOutput | None: ...
    def save_output(
        self,
        tour_id: UUID,
        plan_id: UUID,
        *,
        title: str,
        payload: TourOutputPayload,
        status: TourStatus,
    ) -> Tour: ...


class InsufficientCreditsError(Exception):
    pass


class SupabaseTourRepository:
    def __init__(self, client: Client) -> None:
        self.client = client

    @classmethod
    def from_env(cls) -> "SupabaseTourRepository":
        return cls(create_supabase_client_from_env())

    def create_tour(self, owner_id: UUID, data: TourInput) -> Tour:
        response = self.client.table("tours").insert(
            {"owner_id": str(owner_id), "input": data.model_dump(mode="json")}
        ).execute()
        tour = _one(Tour, response.data, "create tour")
        return self.set_status(tour.id, TourStatus.RESEARCHING)

    def get_tour(self, tour_id: UUID, owner_id: UUID | None = None) -> Tour | None:
        query = self.client.table("tours").select("*").eq("id", str(tour_id))
        if owner_id is not None:
            query = query.eq("owner_id", str(owner_id))
        return _optional_one(Tour, query.limit(1).execute().data)

    def list_tours(self, owner_id: UUID) -> list[TourSummary]:
        response = (
            self.client.table("tours")
            .select("*")
            .eq("owner_id", str(owner_id))
            .order("created_at", desc=True)
            .execute()
        )
        return [TourSummary.model_validate(item) for item in response.data]

    def set_status(
        self, tour_id: UUID, status: TourStatus, details: dict[str, Any] | None = None
    ) -> Tour:
        self.client.rpc(
            "record_tour_status",
            {
                "p_tour_id": str(tour_id),
                "p_status": status.value,
                "p_details": details,
            },
        ).execute()
        tour = self.get_tour(tour_id)
        if tour is None:
            raise RuntimeError("Tour disappeared after status update")
        return tour

    def get_plans(self, tour_id: UUID) -> list[TourPlan]:
        response = (
            self.client.table("tour_plan_revisions")
            .select("*")
            .eq("tour_id", str(tour_id))
            .order("revision")
            .execute()
        )
        return [TourPlan.model_validate(item) for item in response.data]

    def get_plan(self, tour_id: UUID, plan_id: UUID | None = None) -> TourPlan | None:
        query = self.client.table("tour_plan_revisions").select("*").eq(
            "tour_id", str(tour_id)
        )
        if plan_id is not None:
            query = query.eq("id", str(plan_id))
        return _optional_one(
            TourPlan,
            query.order("revision", desc=True).limit(1).execute().data,
        )

    def get_agent_messages(self, tour_id: UUID) -> list[dict[str, Any]]:
        return [
            message
            for plan in self.get_plans(tour_id)
            for message in plan.new_agent_messages
        ]

    def persist_plan(
        self,
        tour_id: UUID,
        *,
        feedback: str | None,
        payload: TourPlanPayload,
        new_agent_messages: list[dict[str, Any]],
    ) -> TourPlan:
        response = self.client.rpc(
            "persist_tour_plan",
            {
                "p_tour_id": str(tour_id),
                "p_feedback": feedback,
                "p_payload": payload.model_dump(mode="json"),
                "p_new_agent_messages": new_agent_messages,
            },
        ).execute()
        plan = self.get_plan(tour_id, UUID(str(response.data)))
        if plan is None:
            raise RuntimeError("Plan disappeared after persistence")
        return plan

    def begin_production(self, tour_id: UUID, plan_id: UUID) -> bool:
        try:
            response = self.client.rpc(
                "begin_tour_production",
                {"p_tour_id": str(tour_id), "p_plan_id": str(plan_id)},
            ).execute()
        except Exception as error:
            if "Insufficient credits" in str(error):
                raise InsufficientCreditsError from error
            raise
        return bool(response.data)

    def get_output(self, tour_id: UUID, plan_id: UUID | None = None) -> TourOutput | None:
        query = self.client.table("tour_outputs").select("*").eq(
            "tour_id", str(tour_id)
        )
        if plan_id is not None:
            query = query.eq("plan_id", str(plan_id))
        return _optional_one(TourOutput, query.order("created_at", desc=True).limit(1).execute().data)

    def save_output(
        self,
        tour_id: UUID,
        plan_id: UUID,
        *,
        title: str,
        payload: TourOutputPayload,
        status: TourStatus,
    ) -> Tour:
        self.client.rpc(
            "save_tour_output",
            {
                "p_tour_id": str(tour_id),
                "p_plan_id": str(plan_id),
                "p_title": title,
                "p_payload": payload.model_dump(mode="json"),
                "p_status": status.value,
            },
        ).execute()
        tour = self.get_tour(tour_id)
        if tour is None:
            raise RuntimeError("Tour disappeared after output persistence")
        return tour


def create_supabase_client_from_env() -> Client:
    url = os.environ.get("SUPABASE_URL") or os.environ.get("API_URL")
    service_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get(
        "SERVICE_ROLE_KEY"
    )
    if not url or not service_key:
        raise RuntimeError(
            "SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set. "
            "For local development, run `npm run dev`."
        )
    return create_client(url, service_key)


def tour_to_read(repository: TourRepository, tour: Tour) -> TourRead:
    plan = repository.get_plan(tour.id)
    output = repository.get_output(tour.id, tour.approved_plan_id)
    return TourRead(
        **tour.model_dump(),
        plan=(
            PlanRead(
                id=plan.id,
                revision=plan.revision,
                feedback=plan.feedback,
                payload=plan.payload,
                created_at=plan.created_at,
            )
            if plan
            else None
        ),
        output=output.payload if output else None,
    )


def _one[T: BaseModel](model: type[T], data: list[Any], operation: str) -> T:
    if len(data) != 1:
        raise RuntimeError(f"Expected one row after {operation}, received {len(data)}")
    return model.model_validate(data[0])


def _optional_one[T: BaseModel](model: type[T], data: list[Any]) -> T | None:
    return model.model_validate(data[0]) if data else None
