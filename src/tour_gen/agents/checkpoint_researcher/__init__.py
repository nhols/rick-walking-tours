from dataclasses import dataclass, field
from itertools import combinations

from pydantic import BaseModel, Field
from pydantic_ai import Agent, AgentRetries, ModelRetry, RunContext, Tool
from pydantic_ai.capabilities.web_search import WebSearch

from tour_gen.geo.distance_matrix import (
    DistanceMatrixEntry,
    GeocodedPlace,
    build_crow_flies_distance_matrix_result,
)
from tour_gen.geo.geoencode import Geocoder


AGENT_MODEL = "google:gemini-3.1-flash-lite"
AGENT_RETRIES: AgentRetries = {"tools": 4, "output": 4}
DISTANCE_TOOL_MAX_RETRIES = 6


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
    max_checkpoint_distance_km: float = 5.0
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

    Use explicit, locally grounded place names. Include enough location context
    in each name to make it unambiguous, such as a park, neighborhood, borough,
    city, or country. For example, use "Skylark Cafe, Wandsworth Common,
    London" instead of "Skylark Cafe".

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

    implausible_distances = [
        entry for entry in distance_matrix_result.distances if entry.distance_km > ctx.deps.max_checkpoint_distance_km
    ]
    if implausible_distances:
        raise ModelRetry(
            "The distance matrix is too spread out for this walking tour. "
            f"Maximum allowed crow-flies distance between any two shortlisted "
            f"places: {ctx.deps.max_checkpoint_distance_km} km. "
            f"Distance matrix returned: {_format_distances(distance_matrix_result.distances)}. "
            f"Distances over the limit: {_format_distances(implausible_distances)}. "
            f"Geocoded places: {_format_geocoded_places(ctx.deps.artifacts.geocoded_places)}. "
            "This usually means one or more place names geocoded to the wrong "
            "city/country, or the shortlist is not compact enough. Call "
            "estimate_place_distances again with more precise place names in "
            "the requested location, or choose a more compact shortlist."
        )

    for entry in distance_matrix_result.distances:
        pair = frozenset((entry.from_place, entry.to_place))
        ctx.deps.artifacts.searched_place_pairs.add(pair)
    return distance_matrix_result.distances


checkpoint_research_agent = Agent[
    CheckpointResearchDeps,
    CheckpointResearchOutput,
](
    model=AGENT_MODEL,
    name="checkpoint_research_agent",
    deps_type=CheckpointResearchDeps,
    output_type=CheckpointResearchOutput,
    retries=AGENT_RETRIES,
    tools=[Tool(estimate_place_distances, max_retries=DISTANCE_TOOL_MAX_RETRIES)],
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
the shortlist of explicit, locally grounded place names you are considering.
Each place name passed to the distance tool must include enough grounding
location context to geocode correctly, such as the park, neighborhood, borough,
city, or country. Do not pass bare or generic names like "the pond", "the
station", "the cafe", or "the war memorial"; use names like "Wandsworth Common
Station, Wandsworth Common, London". Use the returned crow-flies distances to
avoid proposing checkpoints that are implausibly far apart for a walking tour,
and to adapt to any user requests about walking distance, tour duration,
compactness, or pace. Every pair of returned proposals must have been checked
together in the distance tool. If the distance matrix shows very large
distances, treat that as a failed geocode or an unsuitable checkpoint set; try
more precise place names with stronger grounding location context before
returning final proposals.

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


def _format_distances(
    distances: list[DistanceMatrixEntry],
) -> list[dict[str, str | float]]:
    return [
        {
            "from_place": distance.from_place,
            "to_place": distance.to_place,
            "distance_km": distance.distance_km,
        }
        for distance in sorted(
            distances,
            key=lambda distance: distance.distance_km,
            reverse=True,
        )
    ]


def _format_geocoded_places(
    places: dict[str, GeocodedPlace],
) -> list[dict[str, str | float | None]]:
    return [
        {
            "place_name": place.place_name,
            "lat": place.lat,
            "lon": place.lon,
            "formatted_address": place.formatted_address,
        }
        for place in sorted(places.values(), key=lambda place: place.place_name)
    ]
