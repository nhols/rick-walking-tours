import asyncio
from typing import Any
from uuid import UUID

from tour_gen.agents.tour_assistant import SupabaseTourAssistantContextLoader
from tour_gen.backend.assistant import answer_tour_question
from tour_gen.backend.supabase.assistant import SupabaseTourAssistantStore
from tour_gen.backend.supabase.client import create_supabase_client
from tour_worker.models import TourAssistantEvent
from tour_worker.worker import process_event


def handler(event: dict[str, object], _context: object) -> dict[str, Any]:
    if event.get("action") == "ask_tour":
        request = TourAssistantEvent.model_validate(event)
        client = create_supabase_client()
        result = asyncio.run(
            answer_tour_question(
                SupabaseTourAssistantStore(client),
                SupabaseTourAssistantContextLoader(client),
                tour_id=request.tour_id,
                user_id=request.user_id,
                input=request.input,
            )
        )
        return result.model_dump(mode="json")

    asyncio.run(process_event(UUID(str(event["job_id"]))))
    return {"ok": True}
