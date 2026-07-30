from pydantic_ai import RunContext

from tour_gen.agents.checkpoint_researcher.models import CheckpointResearchDeps


def add_location_instruction(ctx: RunContext[CheckpointResearchDeps]) -> str:
    return (
        f"The walking tour must be researched for: {ctx.deps.location}. "
        f"Return between {ctx.deps.min_stops} and {ctx.deps.max_stops} stops. "
        "The maximum allowed crow-flies distance between any two stops is "
        f"{ctx.deps.max_checkpoint_distance_km} km."
    )
