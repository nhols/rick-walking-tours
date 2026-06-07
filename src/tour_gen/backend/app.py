from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException, status
from sqlmodel import Session

from tour_gen.backend.db import create_db_and_tables, get_session
from tour_gen.backend.models import Job, JobCreate, JobEvent, JobRead, JobSummary
from tour_gen.backend.repository import apply_event, create_job, get_job, list_jobs


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    create_db_and_tables()
    yield


app = FastAPI(title="Rick Tour Generator API", lifespan=lifespan)


@app.post("/jobs", response_model=JobRead, status_code=status.HTTP_201_CREATED)
def post_job(
    request: JobCreate,
    session: Session = Depends(get_session),
) -> Job:
    return create_job(session, request)


@app.get("/jobs", response_model=list[JobSummary])
def get_jobs(session: Session = Depends(get_session)) -> list[Job]:
    return list_jobs(session)


@app.get("/jobs/{job_id}", response_model=JobRead)
def get_job_by_id(
    job_id: UUID,
    session: Session = Depends(get_session),
) -> Job:
    job = get_job(session, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@app.post("/jobs/{job_id}/events", response_model=JobRead)
def post_job_event(
    job_id: UUID,
    event: JobEvent,
    session: Session = Depends(get_session),
) -> Job:
    job = get_job(session, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return apply_event(session, job, event)
