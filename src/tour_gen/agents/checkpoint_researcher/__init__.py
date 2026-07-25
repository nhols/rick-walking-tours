from dataclasses import dataclass, field

from pydantic import BaseModel, Field
from pydantic_ai import (
    Agent,
    AgentRetries,
    BinaryContent,
    ModelRetry,
    RunContext,
    Tool,
    ToolReturn,
)
from pydantic_ai.capabilities.web_search import WebSearch

from tour_gen.geo.distance_matrix import (
    DistanceMatrixEntry,
    GeocodedPlace,
    build_crow_flies_distance_matrix_result,
)
from tour_gen.geo.geoencode import GeocodeResult, Geocoder, GeoPosition
from tour_gen.geo.static_map import render_checkpoint_map


AGENT_MODEL = "google:gemini-3.1-flash-lite"
AGENT_RETRIES: AgentRetries = {"tools": 4, "output": 4}
DISTANCE_TOOL_MAX_RETRIES = 6


class CheckpointProposal(BaseModel):
    title: str = Field(min_length=1)
    brief_description: str = Field(min_length=1, max_length=240)
    route_reasoning: str = Field(min_length=1, max_length=240)
    distance_tool_place_name: str = Field(min_length=1)


class CheckpointResearchOutput(BaseModel):
    ordered_checkpoints: list[CheckpointProposal] = Field(min_length=1)
    narrative_arc: str = Field(min_length=1, max_length=600)


@dataclass
class CheckpointResearchArtifacts:
    checked_shortlists: set[frozenset[str]] = field(default_factory=set)
    geocoded_places: dict[str, GeocodedPlace] = field(default_factory=dict)


@dataclass
class CheckpointResearchDeps:
    location: str
    geocoder: Geocoder
    min_stops: int = 2
    max_stops: int = 10
    max_checkpoint_distance_km: float = 10.0
    artifacts: CheckpointResearchArtifacts = field(default_factory=CheckpointResearchArtifacts)
    location_geocode: GeocodeResult | None = None


WEB_SEARCH: WebSearch[CheckpointResearchDeps] = WebSearch(
    search_context_size="high",
    max_uses=8,
)


async def estimate_place_distances(
    ctx: RunContext[CheckpointResearchDeps],
    place_names: list[str],
) -> ToolReturn:
    """Map places and return their one-way crow-flies distances in kilometers.

    Pass the exact checkpoint names you are considering.

    The result only includes one half of the matrix: A>B, never B>A, and never
    the diagonal.
    """
    if ctx.deps.location_geocode is None:
        ctx.deps.location_geocode = await ctx.deps.geocoder.geocode(ctx.deps.location)

    distance_matrix_result = await build_crow_flies_distance_matrix_result(
        place_names=place_names,
        geocoder=ctx.deps.geocoder,
        bias_position=_bias_position(ctx.deps.location_geocode),
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
            "estimate_place_distances again with more precise place names, or "
            "choose a more compact shortlist."
        )

    map_image = await render_checkpoint_map(distance_matrix_result.geocoded_places)
    ctx.deps.artifacts.checked_shortlists.add(frozenset(place_names))
    legend = "\n".join(
        f"{index}. {place.place_name}"
        for index, place in enumerate(
            distance_matrix_result.geocoded_places,
            start=1,
        )
    )
    return ToolReturn(
        return_value=distance_matrix_result.distances,
        content=[
            "Map of the proposed stops. Pin labels correspond to this legend:\n"
            f"{legend}\nUse the map and distances to choose a practical order.",
            BinaryContent(data=map_image, media_type="image/png"),
        ],
    )


checkpoint_research_agent = Agent[
    CheckpointResearchDeps,
    CheckpointResearchOutput,
](
    model=AGENT_MODEL,
    name="checkpoint_research_agent",
    deps_type=CheckpointResearchDeps,
    output_type=CheckpointResearchOutput,
    retries=AGENT_RETRIES,
    defer_model_check=True,
    tools=[Tool(estimate_place_distances, max_retries=DISTANCE_TOOL_MAX_RETRIES)],
    capabilities=[WEB_SEARCH],
    instructions="""
You research and plan a walking tour from the user's request.

Use web search before proposing checkpoints. Look for specific, interesting,
theme-relevant places rather than generic tourist stops. Prefer sources that
help explain why each place belongs on this tour.

Return an ordered list of real physical places a user can visit or stand near.
For each checkpoint, set distance_tool_place_name to the exact place name you
passed to estimate_place_distances, and explain briefly why it appears at that
point in the route. Return a concise narrative arc for the full tour.

Use the estimate_place_distances tool with the complete final shortlist before
returning it. Use its map and crow-flies distances to avoid implausible routes,
choose a practical walking order, and adapt to requests about distance,
duration, compactness, or pace. If the distance matrix shows very large
distances, treat that as a failed geocode or unsuitable shortlist and try more
precise place names.
Do not return distinct checkpoint proposals if the distance matrix shows 0 km
between them. Treat zero-distance pairs as failed geocodes and call
estimate_place_distances again with different, more precise checkpoint names.

Do not write chapter scripts. Do not generate audio. Do not create quizzes.
""".strip(),
)


@checkpoint_research_agent.instructions
def add_location_instruction(ctx: RunContext[CheckpointResearchDeps]) -> str:
    return (
        f"The walking tour must be researched for: {ctx.deps.location}. "
        f"Return between {ctx.deps.min_stops} and {ctx.deps.max_stops} stops. "
        "The maximum allowed crow-flies distance between any two stops is "
        f"{ctx.deps.max_checkpoint_distance_km} km."
    )


@checkpoint_research_agent.output_validator
def validate_checkpoint_distances_were_checked(
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

    returned_shortlist = frozenset(returned_place_names)
    if returned_shortlist not in ctx.deps.artifacts.checked_shortlists:
        raise ModelRetry(
            "Invalid checkpoint proposals. "
            "The complete returned shortlist must be checked and mapped together "
            "with estimate_place_distances before final output. Call the tool "
            "with the final place names, then return distance_tool_place_name "
            "values that exactly match them."
        )

    duplicate_coordinate_groups = _duplicate_coordinate_groups(
        returned_place_names,
        ctx.deps.artifacts.geocoded_places,
    )
    if duplicate_coordinate_groups:
        raise ModelRetry(
            "Invalid checkpoint proposals. "
            "Multiple returned checkpoints geocoded to the same coordinates. "
            f"Duplicate coordinate groups: {duplicate_coordinate_groups}. "
            f"Geocoded places: {_format_geocoded_places(ctx.deps.artifacts.geocoded_places)}. "
            "These distinct checkpoints would appear as zero-distance pairs "
            "in the distance matrix. This usually means one or more checkpoint "
            "names geocoded to a generic fallback location rather than the "
            "intended physical stop. Call estimate_place_distances again with "
            "different, more precise checkpoint names."
        )

    return output


def _duplicate_coordinate_groups(
    place_names: list[str],
    geocoded_places: dict[str, GeocodedPlace],
) -> list[dict[str, object]]:
    places_by_coordinate: dict[tuple[float, float], list[str]] = {}
    for place_name in place_names:
        place = geocoded_places.get(place_name)
        if place is None:
            continue
        coordinate = (place.lat, place.lon)
        places_by_coordinate.setdefault(coordinate, []).append(place_name)

    return [
        {
            "lat": coordinate[0],
            "lon": coordinate[1],
            "place_names": sorted(coordinate_place_names),
        }
        for coordinate, coordinate_place_names in sorted(places_by_coordinate.items())
        if len(coordinate_place_names) > 1
    ]


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


def _bias_position(result: GeocodeResult) -> GeoPosition | None:
    if result.lat is None or result.lon is None:
        return None
    return GeoPosition(lat=result.lat, lon=result.lon)
