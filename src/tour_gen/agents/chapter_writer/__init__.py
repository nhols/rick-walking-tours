from collections import Counter
from dataclasses import dataclass

from pydantic import BaseModel, Field
from pydantic_ai import Agent, ModelRetry, RunContext
from pydantic_ai.capabilities.web_search import WebSearch

from tour_gen.agents.route_planner import RoutePlanOutput


AGENT_MODEL = "google:gemini-3.1-flash-lite"


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
    tts_style: TTSStyle
    chapters: list[Chapter] = Field(min_length=1)


@dataclass
class ChapterWriterDeps:
    route_plan: RoutePlanOutput
    voice_style: str | None = None


WEB_SEARCH: WebSearch[ChapterWriterDeps] = WebSearch(
    search_context_size="high",
    max_uses=12,
)


CHAPTER_WRITER_INSTRUCTIONS = """
You write narration chapters for an ordered walking-tour route.

Use web search to enrich each chapter with grounded details, little facts,
useful recommendations, and interesting online research. Prefer specific
details over generic description.

Return one chapter for every ordered checkpoint. Each chapter title must be
copied exactly from the provided checkpoint title. Write narration that is
designed to be spoken aloud. Each narration should be around 200-1000 words,
roughly 1-5 minutes of speech.

Return one tour-level tts_style for the full audio tour.

The tts_style should match any user-provided voice style guide first and
foremost. Treat that guide as the source of truth for tone, accent, pacing,
energy, delivery, and performance preferences. If the user voice style guide is
not provided, or if it leaves gaps, fill those gaps using the tour's topic,
location, audience, and narrative arc. For example, an Edinburgh Harry Potter
tour would usually suit a British narration style unless the user asks for
something else.

You may use square-bracket performance tags sparingly inside narration where
they improve the spoken result, for example [softly], [brief pause], or
[with a smile]. Do not overuse them.
""".strip()


chapter_writer_agent = Agent[
    ChapterWriterDeps,
    ChapterWriterOutput,
](
    model=AGENT_MODEL,
    name="chapter_writer_agent",
    deps_type=ChapterWriterDeps,
    output_type=ChapterWriterOutput,
    capabilities=[WEB_SEARCH],
    instructions=CHAPTER_WRITER_INSTRUCTIONS,
)


@chapter_writer_agent.instructions
def add_route_plan_instruction(ctx: RunContext[ChapterWriterDeps]) -> str:
    checkpoint_lines = [
        f"- {checkpoint.title}: {checkpoint.reasoning}"
        for checkpoint in ctx.deps.route_plan.ordered_checkpoints
    ]
    instructions = (
        f"Narrative arc: {ctx.deps.route_plan.narrative_arc}\n"
        "Ordered checkpoints:\n"
        + "\n".join(checkpoint_lines)
    )
    if ctx.deps.voice_style:
        instructions += (
            "\n\n"
            "User voice style guide:\n"
            f"{ctx.deps.voice_style}"
        )
    return instructions


@chapter_writer_agent.output_validator
def validate_chapters(
    ctx: RunContext[ChapterWriterDeps],
    output: ChapterWriterOutput,
) -> ChapterWriterOutput:
    expected_titles = [
        checkpoint.title
        for checkpoint in ctx.deps.route_plan.ordered_checkpoints
    ]
    returned_titles = [chapter.title for chapter in output.chapters]

    if Counter(returned_titles) != Counter(expected_titles):
        raise ModelRetry(
            "Invalid chapter titles. "
            f"Expected titles: {expected_titles}. "
            f"Model returned titles: {returned_titles}. "
            "Return one chapter for every expected title exactly once and do "
            "not add extra titles."
        )

    return output
