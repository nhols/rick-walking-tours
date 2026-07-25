from collections import Counter

from pydantic_ai import ModelRetry, RunContext

from tour_gen.agents.chapter_writer.models import (
    ChapterWriterDeps,
    ChapterWriterOutput,
)


TOUR_TITLE_MAX_WORDS = 8


def add_plan_instruction(ctx: RunContext[ChapterWriterDeps]) -> str:
    checkpoint_lines = [
        f"- {checkpoint.title}: {checkpoint.brief_description}\n"
        f"  Exact place: {checkpoint.distance_tool_place_name}\n"
        f"  Route reasoning: {checkpoint.route_reasoning}"
        for checkpoint in ctx.deps.plan.ordered_checkpoints
    ]
    instructions = (
        f"Tour location: {ctx.deps.location}\n"
        f"Narrative arc: {ctx.deps.plan.narrative_arc}\n"
        "Ordered checkpoints:\n" + "\n".join(checkpoint_lines)
    )
    if ctx.deps.voice_style:
        instructions += f"\n\nUser voice style guide:\n{ctx.deps.voice_style}"
    return instructions


def validate_chapters(
    ctx: RunContext[ChapterWriterDeps],
    output: ChapterWriterOutput,
) -> ChapterWriterOutput:
    title_word_count = _word_count(output.tour_title)
    if title_word_count > TOUR_TITLE_MAX_WORDS:
        raise ModelRetry(
            "Invalid tour title. "
            f"The tour_title must be {TOUR_TITLE_MAX_WORDS} words or fewer. "
            f"Model returned {title_word_count} words: {output.tour_title!r}."
        )

    expected_titles = [
        checkpoint.title for checkpoint in ctx.deps.plan.ordered_checkpoints
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


def _word_count(value: str) -> int:
    return len(value.split())
