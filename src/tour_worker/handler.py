import asyncio
from uuid import UUID

from tour_worker.worker import process_event


def handler(event: dict[str, object], _context: object) -> dict[str, bool]:
    asyncio.run(process_event(UUID(str(event["job_id"]))))
    return {"ok": True}
