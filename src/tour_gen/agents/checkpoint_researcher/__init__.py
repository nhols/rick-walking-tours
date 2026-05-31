from dataclasses import dataclass

from pydantic import BaseModel, Field
from pydantic_ai import Agent, RunContext
from pydantic_ai.capabilities.web_search import WebSearch

from tour_gen.geo.distance_matrix import (
    DistanceMatrixEntry,
    build_crow_flies_distance_matrix,
)
from tour_gen.geo.geoencode import Geocoder


AGENT_MODEL = "google:gemini-3.1-flash-lite"


class CheckpointProposal(BaseModel):
    title: str = Field(min_length=1)
    brief_description: str = Field(min_length=1, max_length=240)


class CheckpointResearchOutput(BaseModel):
    proposals: list[CheckpointProposal] = Field(min_length=1)


@dataclass
class CheckpointResearchDeps:
    location: str
    geocoder: Geocoder


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
    return await build_crow_flies_distance_matrix(
        place_names=place_names,
        location=ctx.deps.location,
        geocoder=ctx.deps.geocoder,
    )


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
near.

Use the estimate_place_distances tool before returning final proposals. Give it
the shortlist of place names you are considering. Use the returned crow-flies
distances to avoid proposing checkpoints that are implausibly far apart for a
walking tour, and to adapt to any user requests about walking distance, tour
duration, compactness, or pace.

Do not plan the route. Do not write chapter scripts. Do not generate audio. Do
not create quizzes.
""".strip(),
)


@checkpoint_research_agent.instructions
def add_location_instruction(ctx: RunContext[CheckpointResearchDeps]) -> str:
    return f"The walking tour must be researched for this location: {ctx.deps.location}"
