import asyncio
import os

from fastapi import FastAPI, Header, HTTPException, status

from tour_worker.models import WorkerEvent
from tour_worker.worker import process_event


app = FastAPI(title="Rick local private worker")
_tasks: set[asyncio.Task[None]] = set()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/internal/invoke", status_code=status.HTTP_202_ACCEPTED)
async def invoke(
    event: WorkerEvent,
    x_local_worker_token: str | None = Header(default=None),
) -> dict[str, bool]:
    expected = os.environ.get("LOCAL_WORKER_TOKEN") or os.environ.get(
        "SUPABASE_SERVICE_ROLE_KEY"
    )
    if expected is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Local worker authentication is not configured",
        )
    if x_local_worker_token != expected:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)

    task = asyncio.create_task(process_event(event))
    _tasks.add(task)
    task.add_done_callback(_task_finished)
    return {"accepted": True}


def _task_finished(task: asyncio.Task[None]) -> None:
    _tasks.discard(task)
    if not task.cancelled():
        task.exception()
