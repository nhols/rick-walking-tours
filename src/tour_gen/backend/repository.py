from uuid import UUID

from sqlmodel import Session, col, select

from tour_gen.backend.models import (
    ApproveEvent,
    FeedbackEvent,
    Job,
    JobCreate,
    JobEvent,
    JobStatus,
    Stage,
    StageStatus,
    user_message,
)


STAGE_NAMES = (
    "checkpoint_research",
    "route_planning",
    "chapter_writing",
    "narration",
)


def create_job(session: Session, request: JobCreate) -> Job:
    first_stage = STAGE_NAMES[0]
    job = Job(
        input=request.input,
        status=JobStatus.pending,
        current_stage=first_stage,
    )
    job.stages = [Stage(job_id=job.id, name=name) for name in STAGE_NAMES]

    session.add(job)
    session.commit()
    session.refresh(job)
    for stage in job.stages:
        session.refresh(stage)
    return job


def list_jobs(session: Session) -> list[Job]:
    statement = select(Job).order_by(col(Job.created_at).desc())
    return list(session.exec(statement).all())


def get_job(session: Session, job_id: UUID) -> Job | None:
    return session.get(Job, job_id)


def apply_event(session: Session, job: Job, event: JobEvent) -> Job:
    stage = current_stage(job)
    match event:
        case ApproveEvent():
            stage.status = StageStatus.approved
            _move_to_next_stage(job)
        case FeedbackEvent(message=message):
            stage.state = [*stage.state, user_message(message)]
            stage.status = StageStatus.pending
            job.status = JobStatus.pending

    session.add(job)
    session.commit()
    session.refresh(job)
    for stage in job.stages:
        session.refresh(stage)
    return job


def current_stage(job: Job) -> Stage:
    for stage in job.stages:
        if stage.name == job.current_stage:
            return stage
    raise ValueError(f"Current stage not found: {job.current_stage}")


def _move_to_next_stage(job: Job) -> None:
    current_index = STAGE_NAMES.index(job.current_stage)
    next_index = current_index + 1
    if next_index >= len(STAGE_NAMES):
        job.status = JobStatus.complete
        return

    job.current_stage = STAGE_NAMES[next_index]
    job.status = JobStatus.pending
