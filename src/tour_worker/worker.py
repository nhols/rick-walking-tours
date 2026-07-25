from uuid import UUID

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
from tour_worker.models import TourJob, WorkerEvent


async def process_event(event: WorkerEvent, *, client: Client | None = None) -> None:
    supabase = client or create_supabase_client_from_env()
    data = supabase.rpc(
        "claim_tour_job", {"p_job_id": str(event.job_id)}
    ).execute().data
    if data is None:
        return

    job = TourJob.model_validate(data)
    if job.tour_id != event.tour_id or job.kind != event.kind:
        _fail_job(supabase, event.job_id)
        raise ValueError("Worker event does not match its canonical job")

    repository = SupabaseTourRepository(supabase)
    tour = repository.get_tour(job.tour_id)
    if tour is None:
        _fail_job(supabase, event.job_id)
        raise ValueError("Tour not found for job")

    try:
        if job.kind == "plan":
            await plan_existing_tour(
                repository,
                tour.owner_id,
                tour.id,
                runner=AgentPipeline(),
                geocoder=GoogleMapsGeocoder(),
            )
        elif job.kind == "revise":
            await revise_tour_plan(
                repository,
                tour.owner_id,
                tour.id,
                UUID(str(job.input["plan_id"])),
                str(job.input["feedback"]),
                runner=AgentPipeline(),
                geocoder=GoogleMapsGeocoder(),
            )
        else:
            await approve_and_produce_tour(
                repository,
                tour.owner_id,
                tour.id,
                UUID(str(job.input["plan_id"])),
                runner=AgentPipeline(),
                tts_provider=GeminiTTSProvider(),
                artifact_store=SupabaseArtifactStore(supabase),
            )
    except Exception:
        _fail_job(supabase, event.job_id)
        raise

    supabase.rpc("complete_tour_job", {"p_job_id": str(event.job_id)}).execute()


def _fail_job(client: Client, job_id: UUID) -> None:
    client.rpc("fail_tour_job", {"p_job_id": str(job_id)}).execute()
