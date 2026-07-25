from dataclasses import dataclass

from pydantic import BaseModel, Field

from tour_gen.agents.checkpoint_researcher import CheckpointResearchOutput


class Chapter(BaseModel):
    title: str = Field(min_length=1)
    narration: str = Field(min_length=1)


class TTSStyle(BaseModel):
    scene_setting: str = Field(min_length=1, max_length=600)
    tone: str = Field(min_length=1, max_length=240)
    pace: str = Field(min_length=1, max_length=120)
    accent: str | None = Field(default=None, max_length=120)
    performance_notes: list[str] = Field(default_factory=list)


class ChapterWriterOutput(BaseModel):
    tour_title: str = Field(min_length=1, max_length=80)
    tts_style: TTSStyle
    chapters: list[Chapter] = Field(min_length=1)


@dataclass
class ChapterWriterDeps:
    plan: CheckpointResearchOutput
    location: str
    voice_style: str | None = None
