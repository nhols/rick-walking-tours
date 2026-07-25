from pydantic_ai import BinaryContent, ModelRetry, RunContext, ToolReturn

from tour_gen.agents.checkpoint_researcher.diagnostics import (
    _format_distances,
    _format_geocoded_places,
)
from tour_gen.agents.checkpoint_researcher.models import CheckpointResearchDeps
from tour_gen.geo.distance_matrix import build_crow_flies_distance_matrix_result
from tour_gen.geo.geoencode import GeocodeResult, GeoPosition
from tour_gen.geo.static_map import render_checkpoint_map


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

    result = await build_crow_flies_distance_matrix_result(
        place_names=place_names,
        geocoder=ctx.deps.geocoder,
        bias_position=_bias_position(ctx.deps.location_geocode),
    )
    for place in result.geocoded_places:
        ctx.deps.artifacts.geocoded_places[place.place_name] = place

    implausible_distances = [
        entry
        for entry in result.distances
        if entry.distance_km > ctx.deps.max_checkpoint_distance_km
    ]
    if implausible_distances:
        raise ModelRetry(
            "The distance matrix is too spread out for this walking tour. "
            f"Maximum allowed crow-flies distance between any two shortlisted "
            f"places: {ctx.deps.max_checkpoint_distance_km} km. "
            f"Distance matrix returned: {_format_distances(result.distances)}. "
            f"Distances over the limit: {_format_distances(implausible_distances)}. "
            f"Geocoded places: {_format_geocoded_places(ctx.deps.artifacts.geocoded_places)}. "
            "This usually means one or more place names geocoded to the wrong "
            "city/country, or the shortlist is not compact enough. Call "
            "estimate_place_distances again with more precise place names, or "
            "choose a more compact shortlist."
        )

    map_image = await render_checkpoint_map(result.geocoded_places)
    ctx.deps.artifacts.checked_shortlists.add(frozenset(place_names))
    legend = "\n".join(
        f"{index}. {place.place_name}"
        for index, place in enumerate(result.geocoded_places, start=1)
    )
    return ToolReturn(
        return_value=result.distances,
        content=[
            "Map of the proposed stops. Pin labels correspond to this legend:\n"
            f"{legend}\nUse the map and distances to choose a practical order.",
            BinaryContent(data=map_image, media_type="image/png"),
        ],
    )


def _bias_position(result: GeocodeResult) -> GeoPosition | None:
    if result.lat is None or result.lon is None:
        return None
    return GeoPosition(lat=result.lat, lon=result.lon)
