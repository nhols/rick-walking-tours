from dataclasses import replace
from typing import Any

from pydantic import BaseModel, Field
from pydantic_ai import BinaryContent, ModelMessage, ModelMessagesTypeAdapter
from pydantic_ai.messages import ModelRequest, UserPromptPart
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
    new_agent_messages: list[dict[str, Any]]


async def research_checkpoints(
    *,
    prompt: str,
    location: str,
    geocoder: Geocoder,
    min_stops: int = 2,
    max_stops: int = 10,
    max_checkpoint_distance_km: float = 10.0,
    message_history: list[dict[str, Any]] | None = None,
) -> CheckpointResearchRun:
    artifacts = CheckpointResearchArtifacts()
    restored_history = (
        ModelMessagesTypeAdapter.validate_python(message_history)
        if message_history
        else None
    )
    result = await checkpoint_research_agent.run(
        prompt,
        deps=CheckpointResearchDeps(
            location=location,
            geocoder=geocoder,
            min_stops=min_stops,
            max_stops=max_stops,
            max_checkpoint_distance_km=max_checkpoint_distance_km,
            artifacts=artifacts,
        ),
        message_history=restored_history,
    )
    coordinates_by_name = artifacts.geocoded_places
    coordinates = [
        CheckpointCoordinates(
            place_name=place.place_name,
            lat=place.lat,
            lon=place.lon,
            formatted_address=place.formatted_address,
        )
        for checkpoint in result.output.ordered_checkpoints
        if (place := coordinates_by_name.get(checkpoint.distance_tool_place_name))
        is not None
    ]
    return CheckpointResearchRun(
        output=result.output,
        coordinates=coordinates,
        new_agent_messages=to_jsonable_python(
            _without_binary_content(result.new_messages())
        ),
    )


async def write_chapters(
    *,
    plan: CheckpointResearchOutput,
    location: str,
    voice_style: str | None = None,
) -> ChapterWriterOutput:
    result = await chapter_writer_agent.run(
        "Write the chapters for this approved walking tour.",
        deps=ChapterWriterDeps(
            plan=plan,
            location=location,
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


def _without_binary_content(messages: list[ModelMessage]) -> list[ModelMessage]:
    cleaned: list[ModelMessage] = []
    for message in messages:
        if not isinstance(message, ModelRequest):
            cleaned.append(message)
            continue

        parts = []
        for part in message.parts:
            if isinstance(part, UserPromptPart) and not isinstance(part.content, str):
                content = [
                    item
                    for item in part.content
                    if not isinstance(item, BinaryContent)
                ]
                parts.append(replace(part, content=content))
            else:
                parts.append(part)
        cleaned.append(replace(message, parts=parts))
    return cleaned
