import logging

import logfire
from pydantic import BaseModel

from tour_gen.agents.chapter_writer import (
    ChapterWriterDeps,
    ChapterWriterOutput,
    chapter_writer_agent,
)
from tour_gen.agents.checkpoint_researcher import (
    CheckpointResearchArtifacts,
    CheckpointResearchDeps,
    CheckpointResearchOutput,
    checkpoint_research_agent,
)
from tour_gen.agents.route_planner import (
    RoutePlanOutput,
    RoutePlannerDeps,
    route_planner_agent,
)
from tour_gen.geo.geoencode import Geocoder
from tour_gen.tts.narration import NarrationOutput, narrate_chapters
from tour_gen.tts.provider import TTSProvider


logger = logging.getLogger(__name__)


class CheckpointCoordinates(BaseModel):
    title: str
    distance_tool_place_name: str
    lat: float
    lon: float
    formatted_address: str | None = None


class TourGenerationOutput(BaseModel):
    checkpoint_research: CheckpointResearchOutput
    checkpoint_coordinates: list[CheckpointCoordinates]
    route_plan: RoutePlanOutput
    chapters: ChapterWriterOutput
    narration: NarrationOutput


async def generate_tour(
    user_request: str,
    *,
    location: str,
    geocoder: Geocoder,
    tts_provider: TTSProvider,
    voice: str,
    voice_style: str | None = None,
    tts_model: str | None = None,
    audio_format: str = "wav",
) -> TourGenerationOutput:
    with logfire.span(
        "Generate tour",
        location=location,
        has_voice_style=voice_style is not None,
        audio_format=audio_format,
    ):
        logger.info(
            "Starting tour generation location=%s has_voice_style=%s audio_format=%s",
            location,
            voice_style is not None,
            audio_format,
        )

        checkpoint_research, checkpoint_coordinates = await research_checkpoints(
            user_request, location=location, geocoder=geocoder
        )
        route_plan = await plan_route(checkpoint_research)
        chapters = await write_chapters(route_plan, voice_style=voice_style)
        narration = await narrate_tour(
            chapters, tts_provider=tts_provider, voice=voice, model=tts_model, audio_format=audio_format
        )

        return TourGenerationOutput(
            checkpoint_research=checkpoint_research,
            checkpoint_coordinates=checkpoint_coordinates,
            route_plan=route_plan,
            chapters=chapters,
            narration=narration,
        )


async def research_checkpoints(
    user_request: str,
    *,
    location: str,
    geocoder: Geocoder,
) -> tuple[CheckpointResearchOutput, list[CheckpointCoordinates]]:
    logger.info("Starting checkpoint research")
    checkpoint_artifacts = CheckpointResearchArtifacts()
    result = await checkpoint_research_agent.run(
        user_request,
        deps=CheckpointResearchDeps(
            location=location,
            geocoder=geocoder,
            artifacts=checkpoint_artifacts,
        ),
    )
    checkpoint_research = result.output
    checkpoint_coordinates = _checkpoint_coordinates(
        checkpoint_research,
        checkpoint_artifacts,
    )
    logger.info(
        "Checkpoint research complete checkpoint_count=%s coordinate_count=%s",
        len(checkpoint_research.proposals),
        len(checkpoint_coordinates),
    )
    return checkpoint_research, checkpoint_coordinates


async def plan_route(
    checkpoint_research: CheckpointResearchOutput,
) -> RoutePlanOutput:
    logger.info("Starting route planning")
    result = await route_planner_agent.run(
        "Order the selected checkpoints.",
        deps=RoutePlannerDeps(checkpoints=checkpoint_research.proposals),
    )
    route_plan = result.output
    logger.info(
        "Route planning complete ordered_checkpoint_count=%s",
        len(route_plan.ordered_checkpoints),
    )
    return route_plan


async def write_chapters(
    route_plan: RoutePlanOutput,
    *,
    voice_style: str | None = None,
) -> ChapterWriterOutput:
    logger.info("Starting chapter writing")
    result = await chapter_writer_agent.run(
        "Write narration chapters for the ordered checkpoints.",
        deps=ChapterWriterDeps(route_plan=route_plan, voice_style=voice_style),
    )
    chapters = result.output
    logger.info("Chapter writing complete chapter_count=%s", len(chapters.chapters))
    return chapters


async def narrate_tour(
    chapters: ChapterWriterOutput,
    *,
    tts_provider: TTSProvider,
    voice: str,
    model: str | None = None,
    audio_format: str = "wav",
) -> NarrationOutput:
    logger.info("Starting narration")
    narration = await narrate_chapters(
        chapters,
        tts_provider,
        voice=voice,
        model=model,
        audio_format=audio_format,
    )
    logger.info(
        "Narration complete narrated_chapter_count=%s",
        len(narration.chapters),
    )
    return narration


def _checkpoint_coordinates(
    checkpoint_research: CheckpointResearchOutput,
    checkpoint_artifacts: CheckpointResearchArtifacts,
) -> list[CheckpointCoordinates]:
    coordinates: list[CheckpointCoordinates] = []
    for proposal in checkpoint_research.proposals:
        place = checkpoint_artifacts.geocoded_places.get(proposal.distance_tool_place_name)
        if place is None:
            continue
        coordinates.append(
            CheckpointCoordinates(
                title=proposal.title,
                distance_tool_place_name=proposal.distance_tool_place_name,
                lat=place.lat,
                lon=place.lon,
                formatted_address=place.formatted_address,
            )
        )
    return coordinates
