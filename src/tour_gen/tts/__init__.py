import asyncio
from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, Field

from tour_gen.agents.chapter_writer import Chapter, ChapterWriterOutput


class TTSRequest(BaseModel):
    text: str = Field(min_length=1)
    voice: str = Field(min_length=1)
    model: str | None = None
    audio_format: str = Field(default="mp3", min_length=1)
    instructions: str | None = None
    provider_options: dict[str, Any] = Field(default_factory=dict)


class TTSResult(BaseModel):
    audio: bytes
    media_type: str
    audio_format: str
    voice: str
    model: str | None = None
    duration_seconds: float | None = None
    provider_metadata: dict[str, Any] = Field(default_factory=dict)


class TTSProvider(ABC):
    @abstractmethod
    async def synthesize(self, request: TTSRequest) -> TTSResult:
        """Convert text into speech audio."""


class NarratedChapter(BaseModel):
    title: str = Field(min_length=1)
    narration: str = Field(min_length=1)
    audio: bytes
    media_type: str
    audio_format: str
    voice: str
    model: str | None = None
    duration_seconds: float | None = None


class NarrationOutput(BaseModel):
    chapters: list[NarratedChapter] = Field(min_length=1)


async def narrate_chapters(
    chapter_output: ChapterWriterOutput,
    tts_provider: TTSProvider,
    *,
    voice: str,
    model: str | None = None,
    audio_format: str = "mp3",
    instructions: str | None = None,
    provider_options: dict[str, Any] | None = None,
) -> NarrationOutput:
    chapters = await asyncio.gather(
        *[
            narrate_chapter(
                chapter,
                tts_provider,
                voice=voice,
                model=model,
                audio_format=audio_format,
                instructions=instructions,
                provider_options=provider_options,
            )
            for chapter in chapter_output.chapters
        ]
    )
    return NarrationOutput(chapters=chapters)


async def narrate_chapter(
    chapter: Chapter,
    tts_provider: TTSProvider,
    *,
    voice: str,
    model: str | None = None,
    audio_format: str = "mp3",
    instructions: str | None = None,
    provider_options: dict[str, Any] | None = None,
) -> NarratedChapter:
    result = await tts_provider.synthesize(
        TTSRequest(
            text=chapter.narration,
            voice=voice,
            model=model,
            audio_format=audio_format,
            instructions=instructions,
            provider_options=provider_options or {},
        )
    )

    return NarratedChapter(
        title=chapter.title,
        narration=chapter.narration,
        audio=result.audio,
        media_type=result.media_type,
        audio_format=result.audio_format,
        voice=result.voice,
        model=result.model,
        duration_seconds=result.duration_seconds,
    )
