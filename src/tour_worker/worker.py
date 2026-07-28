from uuid import UUID

import logfire
from supabase import Client

from tour_gen.backend.agent_planner import AgentTourPlanner
from tour_gen.backend.agent_producer import AgentTourProducer
from tour_gen.backend.planning import plan_tour
from tour_gen.backend.production import produce_tour
from tour_gen.backend.supabase.audio import SupabaseAudioStore
from tour_gen.backend.supabase.client import create_supabase_client
from tour_gen.backend.supabase.tours import SupabaseTourStore
from tour_gen.geo.geoencode.google_maps import GoogleMapsGeocoder
from tour_gen.geo.routes.mapbox import MapboxRouter
from tour_gen.tts.gemini import GeminiTTSProvider
from tour_worker.models import (
    ProductionPayload,
    RevisionPayload,
    TourJob,
)


async def process_event(job_id: UUID, *, client: Client | None = None) -> None:
    with logfire.span(
        "tour worker event",
        job_id=str(job_id),
    ):
        client = client or create_supabase_client()
        data = client.rpc("claim_tour_job", {"p_job_id": str(job_id)}).execute().data
        if data is None:
            return

        try:
            job = TourJob.model_validate(data)
            store = SupabaseTourStore(client)
            if isinstance(job.payload, RevisionPayload):
                await plan_tour(
                    store,
                    AgentTourPlanner(GoogleMapsGeocoder(), MapboxRouter()),
                    job.tour_id,
                    plan_id=job.payload.plan_id,
                    feedback=job.payload.feedback,
                )
            elif isinstance(job.payload, ProductionPayload):
                await produce_tour(
                    store,
                    AgentTourProducer(
                        GeminiTTSProvider(),
                        SupabaseAudioStore(client),
                    ),
                    job.tour_id,
                    job.payload.plan_id,
                )
            else:
                await plan_tour(
                    store,
                    AgentTourPlanner(GoogleMapsGeocoder(), MapboxRouter()),
                    job.tour_id,
                )
        except Exception:
            _fail_job(client, job_id)
            raise

        client.rpc("complete_tour_job", {"p_job_id": str(job_id)}).execute()


def _fail_job(client: Client, job_id: UUID) -> None:
    client.rpc("fail_tour_job", {"p_job_id": str(job_id)}).execute()
