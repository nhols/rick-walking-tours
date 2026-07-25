from pydantic_ai import Agent, AgentRetries, Tool
from pydantic_ai.capabilities.web_search import WebSearch

from tour_gen.agents.checkpoint_researcher.models import (
    CheckpointResearchDeps,
    CheckpointResearchOutput,
)
from tour_gen.agents.checkpoint_researcher.tools import estimate_place_distances
from tour_gen.agents.checkpoint_researcher.validation import (
    add_location_instruction,
    validate_checkpoint_distances_were_checked,
)


AGENT_MODEL = "google:gemini-3.1-flash-lite"
AGENT_RETRIES: AgentRetries = {"tools": 4, "output": 4}
DISTANCE_TOOL_MAX_RETRIES = 6


WEB_SEARCH: WebSearch[CheckpointResearchDeps] = WebSearch(
    search_context_size="high",
    max_uses=8,
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

checkpoint_research_agent.instructions(add_location_instruction)
checkpoint_research_agent.output_validator(validate_checkpoint_distances_were_checked)
