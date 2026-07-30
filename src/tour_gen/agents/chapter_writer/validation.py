from collections import Counter

from pydantic_ai import ModelRetry, RunContext

from tour_gen.agents.chapter_writer.models import (
    ChapterWriterDeps,
    ChapterWriterOutput,
)


TOUR_TITLE_MAX_WORDS = 8

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
