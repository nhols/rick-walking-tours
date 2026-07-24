from typing import Any, Protocol
from uuid import UUID

from tour_gen import pipeline
from tour_gen.agents.chapter_writer import ChapterWriterOutput
from tour_gen.agents.checkpoint_researcher import CheckpointResearchOutput
from tour_gen.agents.route_planner import RoutePlanOutput
from tour_gen.backend.artifacts import ArtifactStore
from tour_gen.backend.models import Tour, TourCreate, TourPlan, TourStatus
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
        user_request: str,
        location: str,
        geocoder: Geocoder,
        feedback: str | None = None,
        message_history: list[dict[str, Any]] | None = None,
    ) -> CheckpointResearchRun: ...

    async def plan_route(
        self,
        checkpoint_research: CheckpointResearchOutput,
        *,
        feedback: str | None = None,
    ) -> RoutePlanOutput: ...

    async def write_chapters(
        self,
        *,
        route_plan: RoutePlanOutput,
        checkpoint_research: CheckpointResearchOutput,
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
    plan_route = staticmethod(pipeline.plan_route)
    write_chapters = staticmethod(pipeline.write_chapters)
    narrate_tour = staticmethod(pipeline.narrate_tour)


async def create_and_plan_tour(
    repository: TourRepository,
    owner_id: UUID,
    data: TourCreate,
    *,
    runner: PipelineRunner,
    geocoder: Geocoder,
) -> Tour:
    tour = repository.create_tour(owner_id, data)

    return await plan_existing_tour(
        repository,
        owner_id,
        tour.id,
        runner=runner,
        geocoder=geocoder,
    )


async def plan_existing_tour(
    repository: TourRepository,
    owner_id: UUID,
    tour_id: UUID,
    *,
    runner: PipelineRunner,
    geocoder: Geocoder,
) -> Tour:
    tour = repository.get_tour(tour_id, owner_id)
    if tour is None:
        raise TourNotFoundError(str(tour_id))

    try:
        research_run = await runner.research_checkpoints(
            user_request=tour.request,
            location=tour.location,
            geocoder=geocoder,
        )
        research = research_run.output
        repository.update_tour(
            tour.id,
            {
                "status": TourStatus.PLANNING_ROUTE,
                "progress_message": "Planning the route",
                "progress_current": None,
                "progress_total": None,
                "error_message": None,
            },
        )
        route = await runner.plan_route(research)
        repository.persist_plan(
            tour.id,
            checkpoint_research=research.model_dump(mode="json"),
            route_plan=route.model_dump(mode="json"),
            checkpoints=_checkpoint_payloads(research, research_run.coordinates, route),
            parent_plan_id=None,
            feedback=None,
            checkpoint_agent_messages=research_run.agent_messages,
        )
        completed = repository.get_tour(tour.id, owner_id)
        if completed is None:
            raise RuntimeError("Tour disappeared after plan persistence")
        return completed
    except Exception as error:
        _mark_failed(repository, tour.id, error)
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
    tour = repository.get_tour(tour_id, owner_id)
    if tour is None:
        raise TourNotFoundError(str(tour_id))

    current_plan = repository.get_plan(tour.id, plan_id)
    if (
        current_plan is None
        or current_plan.id != plan_id
        or current_plan.revision != tour.current_plan_revision
    ):
        raise PlanMismatchError("Feedback must target the current tour plan")
    if tour.status not in {TourStatus.AWAITING_REVIEW, TourStatus.RESEARCHING}:
        raise TourStateError(f"Tour cannot accept feedback while {tour.status.value}")
    if tour.current_plan_revision - 1 >= MAX_FEEDBACK_ROUNDS:
        raise TourStateError(
            f"A tour can have at most {MAX_FEEDBACK_ROUNDS} feedback rounds"
        )

    repository.update_tour(
        tour.id,
        {
            "status": TourStatus.RESEARCHING,
            "progress_message": "Revising checkpoints from your feedback",
            "progress_current": None,
            "progress_total": None,
            "error_message": None,
        },
    )

    try:
        research_run = await runner.research_checkpoints(
            user_request=tour.request,
            location=tour.location,
            geocoder=geocoder,
            feedback=feedback,
            message_history=current_plan.checkpoint_agent_messages,
        )
        repository.update_tour(
            tour.id,
            {
                "status": TourStatus.PLANNING_ROUTE,
                "progress_message": "Replanning the route from your feedback",
                "error_message": None,
            },
        )
        route = await runner.plan_route(research_run.output, feedback=feedback)
        repository.persist_plan(
            tour.id,
            checkpoint_research=research_run.output.model_dump(mode="json"),
            route_plan=route.model_dump(mode="json"),
            checkpoints=_checkpoint_payloads(
                research_run.output,
                research_run.coordinates,
                route,
            ),
            parent_plan_id=current_plan.id,
            feedback=feedback,
            checkpoint_agent_messages=research_run.agent_messages,
        )
        revised = repository.get_tour(tour.id, owner_id)
        if revised is None:
            raise RuntimeError("Tour disappeared after feedback persistence")
        return revised
    except Exception as error:
        _restore_review_after_feedback_failure(repository, tour.id, error)
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
    tour = repository.get_tour(tour_id, owner_id)
    if tour is None:
        raise TourNotFoundError(str(tour_id))

    plan_record = repository.get_plan(tour.id, plan_id)
    if (
        plan_record is None
        or plan_record.id != plan_id
        or plan_record.revision != tour.current_plan_revision
    ):
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
    research = CheckpointResearchOutput.model_validate(plan_record.checkpoint_research)
    route = RoutePlanOutput.model_validate(plan_record.route_plan)

    try:
        written = await runner.write_chapters(
            route_plan=route,
            checkpoint_research=research,
            location=tour.location,
            voice_style=tour.voice_style,
        )
        chapter_records = _persist_written_chapters(
            repository,
            tour,
            plan_record,
            written,
        )
        repository.update_tour(
            tour.id,
            {
                "status": TourStatus.GENERATING_AUDIO,
                "progress_message": "Generating chapter audio",
                "progress_current": 0,
                "progress_total": len(chapter_records),
                "error_message": None,
            },
        )
        narrated = await runner.narrate_tour(
            chapters=written,
            tts_provider=tts_provider,
            voice=tour.voice,
            model=tour.tts_model,
            audio_format=tour.audio_format,
        )
        return _persist_audio(
            repository,
            artifact_store,
            tour,
            chapter_records,
            narrated,
        )
    except Exception as error:
        _mark_failed(repository, tour.id, error)
        raise


def _checkpoint_payloads(
    research: CheckpointResearchOutput,
    coordinates: list[CheckpointCoordinates],
    route: RoutePlanOutput,
) -> list[dict[str, Any]]:
    proposals_by_title = {proposal.title: proposal for proposal in research.proposals}
    if len(proposals_by_title) != len(research.proposals):
        raise ValueError("Checkpoint proposal titles must be unique")
    coordinates_by_place = {item.place_name: item for item in coordinates}

    checkpoints: list[dict[str, Any]] = []
    for position, ordered in enumerate(route.ordered_checkpoints, start=1):
        proposal = proposals_by_title.get(ordered.title)
        if proposal is None:
            raise ValueError(f"Route contains an unknown checkpoint: {ordered.title}")
        point = coordinates_by_place.get(proposal.distance_tool_place_name)
        if point is None:
            raise ValueError(
                "Missing coordinates for checkpoint: "
                f"{proposal.distance_tool_place_name}"
            )
        checkpoints.append(
            {
                "position": position,
                "title": proposal.title,
                "description": proposal.brief_description,
                "route_reasoning": ordered.reasoning,
                "distance_tool_place_name": proposal.distance_tool_place_name,
                "lat": point.lat,
                "lon": point.lon,
                "formatted_address": point.formatted_address,
            }
        )
    return checkpoints


def _persist_written_chapters(
    repository: TourRepository,
    tour: Tour,
    plan: TourPlan,
    written: ChapterWriterOutput,
):
    checkpoints_by_title = {
        checkpoint.title: checkpoint
        for checkpoint in repository.get_checkpoints(tour.id, plan.id)
    }
    chapters: list[dict[str, Any]] = []
    for position, chapter in enumerate(written.chapters, start=1):
        checkpoint = checkpoints_by_title.get(chapter.title)
        if checkpoint is None:
            raise ValueError(f"Chapter has no matching checkpoint: {chapter.title}")
        chapters.append(
            {
                "checkpoint_id": str(checkpoint.id),
                "position": position,
                "title": chapter.title,
                "narration": chapter.narration,
            }
        )
    return repository.persist_written_chapters(
        tour.id,
        plan.id,
        tour_title=written.tour_title,
        tts_style=written.tts_style.model_dump(mode="json"),
        chapters=chapters,
    )


def _persist_audio(
    repository: TourRepository,
    artifact_store: ArtifactStore,
    tour: Tour,
    chapter_records,
    narrated: NarrationOutput,
) -> Tour:
    if len(chapter_records) != len(narrated.chapters):
        raise ValueError("Narration output does not match the written chapter count")

    audio_metadata: list[dict[str, Any]] = []
    for position, (record, audio) in enumerate(
        zip(chapter_records, narrated.chapters, strict=True),
        start=1,
    ):
        if record.title != audio.title:
            raise ValueError(f"Narration title does not match chapter: {record.title}")
        audio_path = artifact_store.save_audio(
            owner_id=tour.owner_id,
            tour_id=tour.id,
            position=position,
            audio_format=audio.audio_format,
            media_type=audio.media_type,
            audio=audio.audio,
        )
        audio_metadata.append(
            {
                "chapter_id": str(record.id),
                "audio_path": audio_path,
                "media_type": audio.media_type,
                "audio_format": audio.audio_format,
                "byte_count": len(audio.audio),
                "voice": audio.voice,
                "model": audio.model,
                "duration_seconds": audio.duration_seconds,
            }
        )
    return repository.finalize_audio(tour.id, audio_metadata)


def _mark_failed(
    repository: TourRepository,
    tour_id: UUID,
    error: Exception,
) -> None:
    repository.update_tour(
        tour_id,
        {
            "status": TourStatus.FAILED,
            "progress_message": "Tour generation failed",
            "error_message": str(error)[:2_000],
        },
    )


def _restore_review_after_feedback_failure(
    repository: TourRepository,
    tour_id: UUID,
    error: Exception,
) -> None:
    repository.update_tour(
        tour_id,
        {
            "status": TourStatus.AWAITING_REVIEW,
            "progress_message": "Plan revision failed",
            "progress_current": None,
            "progress_total": None,
            "error_message": str(error)[:2_000],
        },
    )
