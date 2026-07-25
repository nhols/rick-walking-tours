from typing import Any, Protocol
from uuid import UUID, uuid4

from tour_gen import pipeline
from tour_gen.agents.chapter_writer import ChapterWriterOutput
from tour_gen.agents.checkpoint_researcher import (
    CheckpointProposal,
    CheckpointResearchOutput,
)
from tour_gen.backend.artifacts import ArtifactStore
from tour_gen.backend.models import (
    Tour,
    TourChapter,
    TourCheckpoint,
    TourInput,
    TourOutputPayload,
    TourPlan,
    TourPlanPayload,
    TourStatus,
)
from tour_gen.backend.repository import TourRepository
from tour_gen.geo.geoencode import Geocoder
from tour_gen.pipeline import CheckpointCoordinates, CheckpointResearchRun
from tour_gen.tts.narration import NarrationOutput
from tour_gen.tts.provider import TTSProvider


class TourNotFoundError(Exception):
    pass


class TourStateError(Exception):
    pass


class PlanMismatchError(Exception):
    pass


MAX_FEEDBACK_ROUNDS = 3


class PipelineRunner(Protocol):
    async def research_checkpoints(
        self,
        *,
        prompt: str,
        location: str,
        geocoder: Geocoder,
        min_stops: int = 2,
        max_stops: int = 10,
        max_checkpoint_distance_km: float = 10.0,
        message_history: list[dict[str, Any]] | None = None,
    ) -> CheckpointResearchRun: ...

    async def write_chapters(
        self,
        *,
        plan: CheckpointResearchOutput,
        location: str,
        voice_style: str | None = None,
    ) -> ChapterWriterOutput: ...

    async def narrate_tour(
        self,
        *,
        chapters: ChapterWriterOutput,
        tts_provider: TTSProvider,
        voice: str,
        model: str | None = None,
        audio_format: str = "wav",
    ) -> NarrationOutput: ...


class AgentPipeline:
    research_checkpoints = staticmethod(pipeline.research_checkpoints)
    write_chapters = staticmethod(pipeline.write_chapters)
    narrate_tour = staticmethod(pipeline.narrate_tour)


async def create_and_plan_tour(
    repository: TourRepository,
    owner_id: UUID,
    data: TourInput,
    *,
    runner: PipelineRunner,
    geocoder: Geocoder,
) -> Tour:
    tour = repository.create_tour(owner_id, data)
    return await plan_existing_tour(
        repository, owner_id, tour.id, runner=runner, geocoder=geocoder
    )


async def plan_existing_tour(
    repository: TourRepository,
    owner_id: UUID,
    tour_id: UUID,
    *,
    runner: PipelineRunner,
    geocoder: Geocoder,
) -> Tour:
    tour = _tour_or_raise(repository, tour_id, owner_id)
    try:
        return await _generate_plan(
            repository,
            owner_id,
            tour,
            prompt=tour.input.request,
            feedback=None,
            runner=runner,
            geocoder=geocoder,
        )
    except Exception as error:
        _set_failure(repository, tour.id, TourStatus.FAILED, error)
        raise


async def revise_tour_plan(
    repository: TourRepository,
    owner_id: UUID,
    tour_id: UUID,
    plan_id: UUID,
    feedback: str,
    *,
    runner: PipelineRunner,
    geocoder: Geocoder,
) -> Tour:
    tour = _tour_or_raise(repository, tour_id, owner_id)
    current_plan = repository.get_plan(tour.id)
    if current_plan is None or current_plan.id != plan_id:
        raise PlanMismatchError("Feedback must target the current tour plan")
    if tour.status not in {TourStatus.AWAITING_REVIEW, TourStatus.RESEARCHING}:
        raise TourStateError(f"Tour cannot accept feedback while {tour.status.value}")
    if current_plan.revision > MAX_FEEDBACK_ROUNDS:
        raise TourStateError(
            f"A tour can have at most {MAX_FEEDBACK_ROUNDS} feedback rounds"
        )
    if tour.status == TourStatus.AWAITING_REVIEW:
        repository.set_status(tour.id, TourStatus.RESEARCHING)

    try:
        return await _generate_plan(
            repository,
            owner_id,
            tour,
            prompt=feedback,
            feedback=feedback,
            runner=runner,
            geocoder=geocoder,
        )
    except Exception as error:
        _set_failure(repository, tour.id, TourStatus.AWAITING_REVIEW, error)
        raise


async def approve_and_produce_tour(
    repository: TourRepository,
    owner_id: UUID,
    tour_id: UUID,
    plan_id: UUID,
    *,
    runner: PipelineRunner,
    tts_provider: TTSProvider,
    artifact_store: ArtifactStore,
) -> Tour:
    tour = _tour_or_raise(repository, tour_id, owner_id)
    plan = repository.get_plan(tour.id)
    if plan is None or plan.id != plan_id:
        raise PlanMismatchError("The approved plan is not the current tour plan")
    if tour.status == TourStatus.READY and tour.approved_plan_id == plan_id:
        return tour
    if tour.status == TourStatus.AWAITING_REVIEW:
        repository.begin_production(tour.id, plan_id)
    elif not (
        tour.approved_plan_id == plan_id
        and tour.status in {TourStatus.WRITING_CHAPTERS, TourStatus.GENERATING_AUDIO}
    ):
        raise TourStateError(f"Tour cannot be approved while {tour.status.value}")

    try:
        written = await runner.write_chapters(
            plan=_load_plan(plan),
            location=tour.input.location,
            voice_style=tour.input.voice_style,
        )
        output = _build_output(plan, written)
        repository.save_output(
            tour.id,
            plan.id,
            title=written.tour_title,
            payload=output,
            status=TourStatus.GENERATING_AUDIO,
        )
        narrated = await runner.narrate_tour(
            chapters=written,
            tts_provider=tts_provider,
            voice=tour.input.voice,
            model=tour.input.tts_model,
            audio_format=tour.input.audio_format,
        )
        completed = _attach_audio(
            artifact_store, tour, output, narrated
        )
        return repository.save_output(
            tour.id,
            plan.id,
            title=written.tour_title,
            payload=completed,
            status=TourStatus.READY,
        )
    except Exception as error:
        _set_failure(repository, tour.id, TourStatus.FAILED, error)
        raise


async def _generate_plan(
    repository: TourRepository,
    owner_id: UUID,
    tour: Tour,
    *,
    prompt: str,
    feedback: str | None,
    runner: PipelineRunner,
    geocoder: Geocoder,
) -> Tour:
    input = tour.input
    history = repository.get_agent_messages(tour.id)
    run = await runner.research_checkpoints(
        prompt=prompt,
        location=input.location,
        geocoder=geocoder,
        min_stops=input.min_stops,
        max_stops=input.max_stops,
        max_checkpoint_distance_km=input.max_checkpoint_distance_km,
        message_history=history or None,
    )
    repository.persist_plan(
        tour.id,
        feedback=feedback,
        payload=TourPlanPayload(
            narrative_arc=run.output.narrative_arc,
            checkpoints=_checkpoints(run.output, run.coordinates),
        ),
        new_agent_messages=run.new_agent_messages,
    )
    return _tour_or_raise(repository, tour.id, owner_id)


def _checkpoints(
    plan: CheckpointResearchOutput,
    coordinates: list[CheckpointCoordinates],
) -> list[TourCheckpoint]:
    titles = [checkpoint.title for checkpoint in plan.ordered_checkpoints]
    if len(set(titles)) != len(titles):
        raise ValueError("Checkpoint titles must be unique")
    points = {item.place_name: item for item in coordinates}
    result: list[TourCheckpoint] = []
    for position, checkpoint in enumerate(plan.ordered_checkpoints, start=1):
        point = points.get(checkpoint.distance_tool_place_name)
        if point is None:
            raise ValueError(
                f"Missing coordinates for checkpoint: {checkpoint.distance_tool_place_name}"
            )
        result.append(
            TourCheckpoint(
                id=uuid4(),
                position=position,
                title=checkpoint.title,
                description=checkpoint.brief_description,
                route_reasoning=checkpoint.route_reasoning,
                distance_tool_place_name=checkpoint.distance_tool_place_name,
                lat=point.lat,
                lon=point.lon,
                formatted_address=point.formatted_address,
            )
        )
    return result


def _load_plan(plan: TourPlan) -> CheckpointResearchOutput:
    return CheckpointResearchOutput(
        narrative_arc=plan.payload.narrative_arc,
        ordered_checkpoints=[
            CheckpointProposal(
                title=checkpoint.title,
                brief_description=checkpoint.description,
                route_reasoning=checkpoint.route_reasoning,
                distance_tool_place_name=checkpoint.distance_tool_place_name,
            )
            for checkpoint in plan.payload.checkpoints
        ],
    )


def _build_output(plan: TourPlan, written: ChapterWriterOutput) -> TourOutputPayload:
    checkpoints = {item.title: item for item in plan.payload.checkpoints}
    chapters: list[TourChapter] = []
    for position, chapter in enumerate(written.chapters, start=1):
        checkpoint = checkpoints.get(chapter.title)
        if checkpoint is None:
            raise ValueError(f"Chapter has no matching checkpoint: {chapter.title}")
        chapters.append(
            TourChapter(
                id=uuid4(),
                checkpoint_id=checkpoint.id,
                position=position,
                title=chapter.title,
                narration=chapter.narration,
            )
        )
    return TourOutputPayload(
        tts_style=written.tts_style.model_dump(mode="json"),
        chapters=chapters,
    )


def _attach_audio(
    artifact_store: ArtifactStore,
    tour: Tour,
    output: TourOutputPayload,
    narrated: NarrationOutput,
) -> TourOutputPayload:
    if len(output.chapters) != len(narrated.chapters):
        raise ValueError("Narration output does not match the written chapter count")

    chapters: list[TourChapter] = []
    for record, audio in zip(output.chapters, narrated.chapters, strict=True):
        if record.title != audio.title:
            raise ValueError(f"Narration title does not match chapter: {record.title}")
        path = artifact_store.save_audio(
            owner_id=tour.owner_id,
            tour_id=tour.id,
            position=record.position,
            audio_format=audio.audio_format,
            media_type=audio.media_type,
            audio=audio.audio,
        )
        chapters.append(
            record.model_copy(
                update={
                    "audio_path": path,
                    "duration_seconds": audio.duration_seconds,
                }
            )
        )
    return output.model_copy(update={"chapters": chapters})


def _tour_or_raise(
    repository: TourRepository, tour_id: UUID, owner_id: UUID
) -> Tour:
    tour = repository.get_tour(tour_id, owner_id)
    if tour is None:
        raise TourNotFoundError(str(tour_id))
    return tour


def _set_failure(
    repository: TourRepository,
    tour_id: UUID,
    status: TourStatus,
    error: Exception,
) -> None:
    repository.set_status(tour_id, status, {"error": str(error)[:2_000]})
