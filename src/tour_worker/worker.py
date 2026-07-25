from uuid import UUID

from supabase import Client

from tour_gen.backend.agent_planner import AgentTourPlanner
from tour_gen.backend.agent_producer import AgentTourProducer
from tour_gen.backend.planning import plan_tour
from tour_gen.backend.production import produce_tour
from tour_gen.backend.supabase.audio import SupabaseAudioStore
from tour_gen.backend.supabase.client import create_supabase_client
from tour_gen.backend.supabase.tours import SupabaseTourStore
from tour_gen.geo.geoencode.google_maps import GoogleMapsGeocoder
from tour_gen.tts.gemini import GeminiTTSProvider
from tour_worker.models import TourJob, WorkerEvent


async def process_event(event: WorkerEvent, *, client: Client | None = None) -> None:
    client = client or create_supabase_client()
    data = client.rpc(
        "claim_tour_job", {"p_job_id": str(event.job_id)}
    ).execute().data
    if data is None:
        return

    job = TourJob.model_validate(data)
    if job.tour_id != event.tour_id or job.kind != event.kind:
        _fail_job(client, event.job_id)
        raise ValueError("Worker event does not match its job")

    store = SupabaseTourStore(client)
    try:
        if job.kind == "plan":
            await plan_tour(store, AgentTourPlanner(GoogleMapsGeocoder()), job.tour_id)
        elif job.kind == "revise":
            await plan_tour(
                store,
                AgentTourPlanner(GoogleMapsGeocoder()),
                job.tour_id,
                plan_id=UUID(str(job.input["plan_id"])),
                feedback=str(job.input["feedback"]),
            )
        else:
            await produce_tour(
                store,
                AgentTourProducer(
                    GeminiTTSProvider(),
                    SupabaseAudioStore(client),
                ),
                job.tour_id,
                UUID(str(job.input["plan_id"])),
            )
    except Exception:
        _fail_job(client, event.job_id)
        raise

    client.rpc("complete_tour_job", {"p_job_id": str(event.job_id)}).execute()


def _fail_job(client: Client, job_id: UUID) -> None:
    client.rpc("fail_tour_job", {"p_job_id": str(job_id)}).execute()
