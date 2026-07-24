import asyncio
from typing import Any

from tour_worker.models import WorkerEvent
from tour_worker.worker import process_event


def handler(event: dict[str, Any], _context: Any) -> dict[str, bool]:
    asyncio.run(process_event(WorkerEvent.model_validate(event)))
    return {"ok": True}
