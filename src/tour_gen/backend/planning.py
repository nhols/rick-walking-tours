from uuid import UUID

from tour_gen.backend.models import TourStatus
from tour_gen.backend.ports import TourPlanner, TourStore


async def plan_tour(
    store: TourStore,
    planner: TourPlanner,
    tour_id: UUID,
    *,
    plan_id: UUID | None = None,
    feedback: str | None = None,
) -> None:
    tour = store.get_tour(tour_id)
    if tour is None:
        raise ValueError("Tour not found")

    current_plan = store.get_plan(tour_id)
    if feedback is None:
        prompt = tour.input.request
        failure_status = TourStatus.FAILED
    else:
        if current_plan is None or current_plan.id != plan_id:
            raise ValueError("Feedback must target the current tour plan")
        prompt = feedback
        failure_status = TourStatus.AWAITING_REVIEW

    try:
        generated = await planner.plan(
            tour.input,
            prompt,
            store.get_agent_messages(tour_id),
        )
        store.save_plan(tour_id, feedback=feedback, generated=generated)
    except Exception as error:
        store.set_status(
            tour_id,
            failure_status,
            {"error": str(error)[:2_000]},
        )
        raise
