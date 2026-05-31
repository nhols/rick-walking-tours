import logging

from pydantic import BaseModel

from tour_gen.agents.chapter_writer import (
    ChapterWriterDeps,
    ChapterWriterOutput,
    chapter_writer_agent,
)
from tour_gen.agents.checkpoint_researcher import (
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


class TourGenerationOutput(BaseModel):
    checkpoint_research: CheckpointResearchOutput
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
    logger.info(
        "Starting tour generation location=%s has_voice_style=%s audio_format=%s",
        location,
        voice_style is not None,
        audio_format,
    )

    logger.info("Starting checkpoint research")
    checkpoint_research_result = await checkpoint_research_agent.run(
        user_request,
        deps=CheckpointResearchDeps(location=location, geocoder=geocoder),
    )
    checkpoint_research = checkpoint_research_result.output
    logger.info(
        "Checkpoint research complete checkpoint_count=%s",
        len(checkpoint_research.proposals),
    )

    logger.info("Starting route planning")
    route_plan_result = await route_planner_agent.run(
        "Order the selected checkpoints.",
        deps=RoutePlannerDeps(checkpoints=checkpoint_research.proposals),
    )
    route_plan = route_plan_result.output
    logger.info(
        "Route planning complete ordered_checkpoint_count=%s",
        len(route_plan.ordered_checkpoints),
    )

    logger.info("Starting chapter writing")
    chapter_result = await chapter_writer_agent.run(
        "Write narration chapters for the ordered checkpoints.",
        deps=ChapterWriterDeps(route_plan=route_plan, voice_style=voice_style),
    )
    chapters = chapter_result.output
    logger.info("Chapter writing complete chapter_count=%s", len(chapters.chapters))

    logger.info("Starting narration")
    narration = await narrate_chapters(
        chapters,
        tts_provider,
        voice=voice,
        model=tts_model,
        audio_format=audio_format,
    )
    logger.info(
        "Narration complete narrated_chapter_count=%s",
        len(narration.chapters),
    )

    return TourGenerationOutput(
        checkpoint_research=checkpoint_research,
        route_plan=route_plan,
        chapters=chapters,
        narration=narration,
    )
