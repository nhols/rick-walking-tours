from supabase import Client

from tour_gen.backend.artifacts import SupabaseArtifactStore
from tour_gen.backend.repository import (
    SupabaseTourRepository,
    create_supabase_client_from_env,
)
from tour_gen.backend.service import (
    AgentPipeline,
    approve_and_produce_tour,
    plan_existing_tour,
    revise_tour_plan,
)
from tour_gen.geo.geoencode.google_maps import GoogleMapsGeocoder
from tour_gen.tts.gemini import GeminiTTSProvider
from tour_worker.models import GenerationRun, WorkerEvent


async def process_event(event: WorkerEvent, *, client: Client | None = None) -> None:
    supabase = client or create_supabase_client_from_env()
    run_data = supabase.rpc(
        "claim_generation_run",
        {"p_run_id": str(event.run_id)},
    ).execute().data
    if run_data is None:
        return

    run = GenerationRun.model_validate(run_data)
    if run.tour_id != event.tour_id or run.action != event.action:
        error = "Worker event does not match its canonical generation run"
        _fail_run(supabase, event, error)
        raise ValueError(error)

    repository = SupabaseTourRepository(supabase)
    tour = repository.get_tour(run.tour_id)
    if tour is None:
        error = "Tour not found for generation run"
        _fail_run(supabase, event, error)
        raise ValueError(error)

    try:
        if run.action == "produce":
            if run.plan_id is None:
                raise ValueError("Production run has no plan")
            await approve_and_produce_tour(
                repository,
                tour.owner_id,
                tour.id,
                run.plan_id,
                runner=AgentPipeline(),
                tts_provider=GeminiTTSProvider(),
                artifact_store=SupabaseArtifactStore(supabase),
            )
        elif run.plan_id is not None:
            if run.feedback is None:
                raise ValueError("Revision run has no feedback")
            await revise_tour_plan(
                repository,
                tour.owner_id,
                tour.id,
                run.plan_id,
                run.feedback,
                runner=AgentPipeline(),
                geocoder=GoogleMapsGeocoder(),
            )
        else:
            await plan_existing_tour(
                repository,
                tour.owner_id,
                tour.id,
                runner=AgentPipeline(),
                geocoder=GoogleMapsGeocoder(),
            )
    except Exception as error:
        _fail_run(supabase, event, str(error))
        raise

    supabase.rpc(
        "complete_generation_run",
        {"p_run_id": str(event.run_id)},
    ).execute()


def _fail_run(client: Client, event: WorkerEvent, message: str) -> None:
    client.rpc(
        "fail_generation_run",
        {
            "p_run_id": str(event.run_id),
            "p_error_message": message or "Worker failed",
        },
    ).execute()
