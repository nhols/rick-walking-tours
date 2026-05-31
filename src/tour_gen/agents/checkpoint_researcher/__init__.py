from dataclasses import dataclass

from pydantic import BaseModel, Field
from pydantic_ai import Agent, RunContext
from pydantic_ai.capabilities.web_search import WebSearch

from tour_gen.geoencode import GeocodeResult, Geocoder


AGENT_MODEL = "google:gemini-2.5-flash"


class CheckpointProposal(BaseModel):
    title: str = Field(min_length=1)
    brief_description: str = Field(min_length=1, max_length=240)
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)


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


async def geocode_checkpoint(
    ctx: RunContext[CheckpointResearchDeps],
    query: str,
) -> GeocodeResult:
    return await ctx.deps.geocoder.geocode(query)


checkpoint_research_agent = Agent[
    CheckpointResearchDeps,
    CheckpointResearchOutput,
](
    model=AGENT_MODEL,
    name="checkpoint_research_agent",
    deps_type=CheckpointResearchDeps,
    output_type=CheckpointResearchOutput,
    tools=[geocode_checkpoint],
    capabilities=[WEB_SEARCH],
    instructions="""
You propose walking-tour checkpoint candidates from a single user request.

Use web search before proposing checkpoints. Look for specific, interesting,
theme-relevant places rather than generic tourist stops. Prefer sources that
help explain why each place belongs on this tour.

Return concise proposals for real physical places a user can visit or stand
near. Geocode every checkpoint before returning it. Only return checkpoints
with latitude and longitude.

Do not plan the route. Do not write chapter scripts. Do not generate audio. Do
not create quizzes.
""".strip(),
)


@checkpoint_research_agent.instructions
def add_location_instruction(ctx: RunContext[CheckpointResearchDeps]) -> str:
    return f"The walking tour must be researched for this location: {ctx.deps.location}"
