from uuid import UUID

from tour_gen.backend.models import TourStatus
from tour_gen.backend.ports import TourProducer, TourStore


async def produce_tour(
    store: TourStore,
    producer: TourProducer,
    tour_id: UUID,
    plan_id: UUID,
) -> None:
    tour = store.get_tour(tour_id)
    plan = store.get_plan(tour_id)
    if tour is None or plan is None:
        raise ValueError("Tour or plan not found")
    if plan.id != plan_id or tour.approved_plan_id != plan_id:
        raise ValueError("Production must use the approved current plan")
    if tour.status == TourStatus.READY:
        return

    try:
        written = await producer.write(tour.input, plan.payload)
        store.save_output(
            tour_id,
            plan_id,
            title=written.title,
            output=written.output,
            status=TourStatus.GENERATING_AUDIO,
        )
        completed = await producer.narrate(
            tour.owner_id,
            tour_id,
            tour.input,
            written,
        )
        store.save_output(
            tour_id,
            plan_id,
            title=written.title,
            output=completed,
            status=TourStatus.READY,
        )
    except Exception as error:
        store.set_status(
            tour_id,
            TourStatus.FAILED,
            {"error": str(error)[:2_000]},
        )
        raise
