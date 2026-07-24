from typing import Any

from pydantic import BaseModel, Field
from pydantic_ai import ModelMessagesTypeAdapter
from pydantic_core import to_jsonable_python

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


class CheckpointCoordinates(BaseModel):
    place_name: str = Field(min_length=1)
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    formatted_address: str | None = None


class CheckpointResearchRun(BaseModel):
    output: CheckpointResearchOutput
    coordinates: list[CheckpointCoordinates]
    agent_messages: list[dict[str, Any]]


async def research_checkpoints(
    *,
    user_request: str,
    location: str,
    geocoder: Geocoder,
    feedback: str | None = None,
    message_history: list[dict[str, Any]] | None = None,
) -> CheckpointResearchRun:
    artifacts = CheckpointResearchArtifacts()
    restored_history = (
        ModelMessagesTypeAdapter.validate_python(message_history)
        if message_history
        else None
    )
    prompt = user_request
    if feedback is not None:
        prompt = (
            "Revise the complete checkpoint shortlist in response to this user "
            f"feedback.\n\nOriginal request:\n{user_request}\n\n"
            f"Latest feedback:\n{feedback}\n\n"
            "Return a complete replacement shortlist, not a partial edit. Re-run "
            "estimate_place_distances with the final shortlist before returning it."
        )
    result = await checkpoint_research_agent.run(
        prompt,
        deps=CheckpointResearchDeps(
            location=location,
            geocoder=geocoder,
            artifacts=artifacts,
        ),
        message_history=restored_history,
    )
    coordinates = [
        CheckpointCoordinates(
            place_name=place.place_name,
            lat=place.lat,
            lon=place.lon,
            formatted_address=place.formatted_address,
        )
        for place in artifacts.geocoded_places.values()
    ]
    return CheckpointResearchRun(
        output=result.output,
        coordinates=coordinates,
        agent_messages=to_jsonable_python(result.all_messages()),
    )


async def plan_route(
    checkpoint_research: CheckpointResearchOutput,
    *,
    feedback: str | None = None,
) -> RoutePlanOutput:
    prompt = "Order these checkpoints into a coherent walking tour."
    if feedback is not None:
        prompt += f"\n\nThe user's feedback on the previous plan was:\n{feedback}"
    result = await route_planner_agent.run(
        prompt,
        deps=RoutePlannerDeps(checkpoints=checkpoint_research.proposals),
    )
    return result.output


async def write_chapters(
    *,
    route_plan: RoutePlanOutput,
    checkpoint_research: CheckpointResearchOutput,
    location: str,
    voice_style: str | None = None,
) -> ChapterWriterOutput:
    result = await chapter_writer_agent.run(
        "Write the chapters for this approved walking tour.",
        deps=ChapterWriterDeps(
            route_plan=route_plan,
            location=location,
            checkpoints=checkpoint_research.proposals,
            voice_style=voice_style,
        ),
    )
    return result.output


async def narrate_tour(
    *,
    chapters: ChapterWriterOutput,
    tts_provider: TTSProvider,
    voice: str,
    model: str | None = None,
    audio_format: str = "wav",
) -> NarrationOutput:
    return await narrate_chapters(
        chapters,
        tts_provider,
        voice=voice,
        model=model,
        audio_format=audio_format,
    )
