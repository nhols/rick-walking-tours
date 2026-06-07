import json

from pydantic import BaseModel, JsonValue
from pydantic_ai.messages import ModelMessage, ModelRequest, UserPromptPart
from sqlmodel import Session

from tour_gen.agents.chapter_writer import ChapterWriterDeps, ChapterWriterOutput, chapter_writer_agent
from tour_gen.agents.checkpoint_researcher import (
    CheckpointResearchArtifacts,
    CheckpointResearchDeps,
    CheckpointResearchOutput,
    checkpoint_research_agent,
)
from tour_gen.agents.route_planner import RoutePlanOutput, RoutePlannerDeps, route_planner_agent
from tour_gen.backend.models import Job, JobStatus, Stage, StageStatus, app_message
from tour_gen.backend.repository import STAGE_NAMES, current_stage
from tour_gen.geo.geoencode.mapbox import MapboxGeocoder


APP_RESULT_PREFIX = "APP_STAGE_RESULT:"


class StageResultEnvelope(BaseModel):
    stage: str
    output: JsonValue


async def advance_job(session: Session, job: Job) -> Job:
    while job.status == JobStatus.pending:
        stage = current_stage(job)
        match stage.name:
            case "checkpoint_research":
                await _run_checkpoint_research(job, stage)
                job.status = JobStatus.awaiting_input
                break
            case "route_planning":
                await _run_route_planning(job, stage)
                _move_to_next_stage(job)
            case "chapter_writing":
                await _run_chapter_writing(job, stage)
                _move_to_next_stage(job)
            case "narration":
                stage.status = StageStatus.complete
                job.status = JobStatus.complete
                break
            case unknown_stage:
                raise ValueError(f"Unknown stage: {unknown_stage}")

    session.add(job)
    session.commit()
    session.refresh(job)
    for stage in job.stages:
        session.refresh(stage)
    return job


async def _run_checkpoint_research(job: Job, stage: Stage) -> None:
    stage.status = StageStatus.running
    artifacts = CheckpointResearchArtifacts()
    history = _agent_history(stage.state)
    result = await checkpoint_research_agent.run(
        _checkpoint_prompt(job),
        message_history=history or None,
        deps=CheckpointResearchDeps(
            location=job.input.location,
            geocoder=MapboxGeocoder(),
            artifacts=artifacts,
        ),
    )
    stage.state = [
        *result.all_messages(),
        _result_message("checkpoint_research", result.output),
    ]
    stage.status = StageStatus.awaiting_approval


async def _run_route_planning(job: Job, stage: Stage) -> None:
    checkpoint_output = _stage_result(
        _stage(job, "checkpoint_research"),
        "checkpoint_research",
        CheckpointResearchOutput,
    )
    stage.status = StageStatus.running
    result = await route_planner_agent.run(
        "Order the selected checkpoints.",
        deps=RoutePlannerDeps(checkpoints=checkpoint_output.proposals),
    )
    stage.state = [
        *result.all_messages(),
        _result_message("route_planning", result.output),
    ]
    stage.status = StageStatus.complete


async def _run_chapter_writing(job: Job, stage: Stage) -> None:
    route_plan = _stage_result(
        _stage(job, "route_planning"),
        "route_planning",
        RoutePlanOutput,
    )
    stage.status = StageStatus.running
    result = await chapter_writer_agent.run(
        "Write narration chapters for the ordered checkpoints.",
        deps=ChapterWriterDeps(route_plan=route_plan),
    )
    stage.state = [
        *result.all_messages(),
        _result_message("chapter_writing", result.output),
    ]
    stage.status = StageStatus.complete


def _checkpoint_prompt(job: Job) -> str:
    if _agent_history(_stage(job, "checkpoint_research").state):
        return "Revise the checkpoint proposals using the latest user feedback."

    return f"Location: {job.input.location}\nTour request: {job.input.description}"


def _move_to_next_stage(job: Job) -> None:
    current_index = STAGE_NAMES.index(job.current_stage)
    next_index = current_index + 1
    if next_index >= len(STAGE_NAMES):
        job.status = JobStatus.complete
        return

    job.current_stage = STAGE_NAMES[next_index]
    job.status = JobStatus.pending


def _stage(job: Job, name: str) -> Stage:
    for stage in job.stages:
        if stage.name == name:
            return stage
    raise ValueError(f"Stage not found: {name}")


def _agent_history(messages: list[ModelMessage]) -> list[ModelMessage]:
    return [
        message
        for message in messages
        if not _is_app_result_message(message)
    ]


def _result_message(stage_name: str, output: BaseModel) -> ModelRequest:
    envelope = StageResultEnvelope(
        stage=stage_name,
        output=output.model_dump(mode="json"),
    )
    return app_message(f"{APP_RESULT_PREFIX}{envelope.model_dump_json()}")


def _stage_result[T: BaseModel](
    stage: Stage,
    stage_name: str,
    output_type: type[T],
) -> T:
    for message in reversed(stage.state):
        content = _message_text(message)
        if not content.startswith(APP_RESULT_PREFIX):
            continue

        envelope = StageResultEnvelope.model_validate_json(
            content.removeprefix(APP_RESULT_PREFIX)
        )
        if envelope.stage != stage_name:
            continue

        return output_type.model_validate(envelope.output)

    raise ValueError(f"No result found for stage: {stage_name}")


def _is_app_result_message(message: ModelMessage) -> bool:
    return _message_text(message).startswith(APP_RESULT_PREFIX)


def _message_text(message: ModelMessage) -> str:
    if not isinstance(message, ModelRequest):
        return ""

    parts = message.parts
    if len(parts) != 1:
        return ""

    part = parts[0]
    if not isinstance(part, UserPromptPart):
        return ""

    content = part.content
    return content if isinstance(content, str) else ""
