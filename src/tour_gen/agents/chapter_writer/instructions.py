from pydantic_ai import RunContext

from tour_gen.agents.chapter_writer.models import ChapterWriterDeps


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
