from dataclasses import dataclass, field
from itertools import combinations

from pydantic import BaseModel, Field
from pydantic_ai import Agent, ModelRetry, RunContext
from pydantic_ai.capabilities.web_search import WebSearch

from tour_gen.geo.distance_matrix import (
    DistanceMatrixEntry,
    GeocodedPlace,
    build_crow_flies_distance_matrix_result,
)
from tour_gen.geo.geoencode import Geocoder


AGENT_MODEL = "google:gemini-3.1-flash-lite"


class CheckpointProposal(BaseModel):
    title: str = Field(min_length=1)
    brief_description: str = Field(min_length=1, max_length=240)
    distance_tool_place_name: str = Field(min_length=1)


class CheckpointResearchOutput(BaseModel):
    proposals: list[CheckpointProposal] = Field(min_length=1)


@dataclass
class CheckpointResearchArtifacts:
    searched_place_pairs: set[frozenset[str]] = field(default_factory=set)
    geocoded_places: dict[str, GeocodedPlace] = field(default_factory=dict)


@dataclass
class CheckpointResearchDeps:
    location: str
    geocoder: Geocoder
    artifacts: CheckpointResearchArtifacts = field(default_factory=CheckpointResearchArtifacts)


WEB_SEARCH: WebSearch[CheckpointResearchDeps] = WebSearch(
    search_context_size="high",
    max_uses=8,
)


async def estimate_place_distances(
    ctx: RunContext[CheckpointResearchDeps],
    place_names: list[str],
) -> list[DistanceMatrixEntry]:
    """Return one-way crow-flies distances between place names in kilometers.

    The result only includes one half of the matrix: A>B, never B>A, and never
    the diagonal.
    """
    distance_matrix_result = await build_crow_flies_distance_matrix_result(
        place_names=place_names,
        location=ctx.deps.location,
        geocoder=ctx.deps.geocoder,
    )
    for place in distance_matrix_result.geocoded_places:
        ctx.deps.artifacts.geocoded_places[place.place_name] = place
    for entry in distance_matrix_result.distances:
        ctx.deps.artifacts.searched_place_pairs.add(frozenset((entry.from_place, entry.to_place)))
    return distance_matrix_result.distances


checkpoint_research_agent = Agent[
    CheckpointResearchDeps,
    CheckpointResearchOutput,
](
    model=AGENT_MODEL,
    name="checkpoint_research_agent",
    deps_type=CheckpointResearchDeps,
    output_type=CheckpointResearchOutput,
    tools=[estimate_place_distances],
    capabilities=[WEB_SEARCH],
    instructions="""
You propose walking-tour checkpoint candidates from a single user request.

Use web search before proposing checkpoints. Look for specific, interesting,
theme-relevant places rather than generic tourist stops. Prefer sources that
help explain why each place belongs on this tour.

Return concise proposals for real physical places a user can visit or stand
near. For each proposal, set distance_tool_place_name to the exact place name
you passed to estimate_place_distances for that checkpoint.

Use the estimate_place_distances tool before returning final proposals. Give it
the shortlist of place names you are considering. Use the returned crow-flies
distances to avoid proposing checkpoints that are implausibly far apart for a
walking tour, and to adapt to any user requests about walking distance, tour
duration, compactness, or pace. Every pair of returned proposals must have been
checked together in the distance tool.

Do not plan the route. Do not write chapter scripts. Do not generate audio. Do
not create quizzes.
""".strip(),
)


@checkpoint_research_agent.instructions
def add_location_instruction(ctx: RunContext[CheckpointResearchDeps]) -> str:
    return f"The walking tour must be researched for this location: {ctx.deps.location}"


@checkpoint_research_agent.output_validator
def validate_checkpoint_distances_were_checked(
    ctx: RunContext[CheckpointResearchDeps],
    output: CheckpointResearchOutput,
) -> CheckpointResearchOutput:
    returned_place_names = [proposal.distance_tool_place_name for proposal in output.proposals]
    returned_pairs = {frozenset(pair) for pair in combinations(returned_place_names, 2)}

    duplicate_place_names = sorted(
        {place_name for place_name in returned_place_names if returned_place_names.count(place_name) > 1}
    )
    if duplicate_place_names:
        raise ModelRetry(
            "Invalid checkpoint proposals. "
            "Each proposal must use a distinct distance_tool_place_name. "
            f"Duplicate place names: {duplicate_place_names}. "
            "Set distance_tool_place_name to the exact distinct place name "
            "searched with estimate_place_distances for each checkpoint."
        )

    missing_pairs = returned_pairs - ctx.deps.artifacts.searched_place_pairs
    if missing_pairs:
        raise ModelRetry(
            "Invalid checkpoint proposals. "
            "Every pair of returned checkpoints must have been checked together "
            "with estimate_place_distances before final output. "
            f"Returned checkpoint place pairs: {_format_pairs(returned_pairs)}. "
            f"Searched place pairs: {_format_pairs(ctx.deps.artifacts.searched_place_pairs)}. "
            f"Missing searched pairs: {_format_pairs(missing_pairs)}. "
            "Call estimate_place_distances with the final shortlist of place "
            "names, then return distance_tool_place_name values that exactly "
            "match those searched place names."
        )

    return output


def _format_pairs(pairs: set[frozenset[str]]) -> list[tuple[str, str]]:
    formatted_pairs: list[tuple[str, str]] = []
    for pair in pairs:
        if len(pair) != 2:
            continue
        first, second = sorted(pair)
        formatted_pairs.append((first, second))
    return sorted(formatted_pairs)
