from pydantic_ai import ModelRetry, RunContext

from tour_gen.agents.checkpoint_researcher.diagnostics import (
    _duplicate_coordinate_groups,
    _format_geocoded_places,
)
from tour_gen.agents.checkpoint_researcher.models import (
    CheckpointResearchDeps,
    CheckpointResearchOutput,
)

def validate_checkpoint_output(
    ctx: RunContext[CheckpointResearchDeps],
    output: CheckpointResearchOutput,
) -> CheckpointResearchOutput:
    checkpoints = output.ordered_checkpoints
    if not ctx.deps.min_stops <= len(checkpoints) <= ctx.deps.max_stops:
        raise ModelRetry(
            "Invalid checkpoint count. "
            f"Return between {ctx.deps.min_stops} and {ctx.deps.max_stops} "
            f"stops; returned {len(checkpoints)}."
        )

    returned_place_names = [
        checkpoint.distance_tool_place_name for checkpoint in checkpoints
    ]
    duplicate_place_names = sorted(
        {
            place_name
            for place_name in returned_place_names
            if returned_place_names.count(place_name) > 1
        }
    )
    if duplicate_place_names:
        raise ModelRetry(
            "Invalid checkpoint proposals. "
            "Each proposal must use a distinct distance_tool_place_name. "
            f"Duplicate place names: {duplicate_place_names}. "
            "Set distance_tool_place_name to the exact distinct place name "
            "searched with estimate_place_distances for each checkpoint."
        )

    if frozenset(returned_place_names) not in ctx.deps.artifacts.checked_shortlists:
        raise ModelRetry(
            "Invalid checkpoint proposals. "
            "The complete returned shortlist must be checked and mapped together "
            "with estimate_place_distances before final output. Call the tool "
            "with the final place names, then return distance_tool_place_name "
            "values that exactly match them."
        )

    duplicate_coordinates = _duplicate_coordinate_groups(
        returned_place_names,
        ctx.deps.artifacts.geocoded_places,
    )
    if duplicate_coordinates:
        raise ModelRetry(
            "Invalid checkpoint proposals. "
            "Multiple returned checkpoints geocoded to the same coordinates. "
            f"Duplicate coordinate groups: {duplicate_coordinates}. "
            f"Geocoded places: {_format_geocoded_places(ctx.deps.artifacts.geocoded_places)}. "
            "These distinct checkpoints would appear as zero-distance pairs "
            "in the distance matrix. This usually means one or more checkpoint "
            "names geocoded to a generic fallback location rather than the "
            "intended physical stop. Call estimate_place_distances again with "
            "different, more precise checkpoint names."
        )

    return output
