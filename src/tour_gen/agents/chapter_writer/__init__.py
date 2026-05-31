from collections import Counter
from dataclasses import dataclass

from pydantic import BaseModel, Field
from pydantic_ai import Agent, ModelRetry, RunContext

from tour_gen.agents.route_planner import RoutePlanOutput


AGENT_MODEL = "google:gemini-2.5-flash"


class Chapter(BaseModel):
    title: str = Field(min_length=1)
    narration: str = Field(min_length=1)


class ChapterWriterOutput(BaseModel):
    chapters: list[Chapter] = Field(min_length=1)


@dataclass
class ChapterWriterDeps:
    route_plan: RoutePlanOutput


chapter_writer_agent = Agent[
    ChapterWriterDeps,
    ChapterWriterOutput,
](
    model=AGENT_MODEL,
    name="chapter_writer_agent",
    deps_type=ChapterWriterDeps,
    output_type=ChapterWriterOutput,
    instructions="""
You write narration chapters for an ordered walking-tour route.

Return one chapter for every ordered checkpoint. Each chapter title must be
copied exactly from the provided checkpoint title. Write narration that is
designed to be spoken aloud.
""".strip(),
)


@chapter_writer_agent.instructions
def add_route_plan_instruction(ctx: RunContext[ChapterWriterDeps]) -> str:
    checkpoint_lines = [
        f"- {checkpoint.title}: {checkpoint.reasoning}"
        for checkpoint in ctx.deps.route_plan.ordered_checkpoints
    ]
    return (
        f"Narrative arc: {ctx.deps.route_plan.narrative_arc}\n"
        "Ordered checkpoints:\n"
        + "\n".join(checkpoint_lines)
    )


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
