from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, Field

from tour_gen.agents.chapter_writer import TTSStyle


class TTSRequest(BaseModel):
    text: str = Field(min_length=1)
    voice: str = Field(min_length=1)
    model: str | None = None
    audio_format: str = Field(default="mp3", min_length=1)
    instructions: str | None = None
    tts_style: TTSStyle | None = None
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
