from collections import Counter
from dataclasses import dataclass

from pydantic import BaseModel, Field
from pydantic_ai import Agent, AgentRetries, ModelRetry, RunContext

from tour_gen.agents.checkpoint_researcher import CheckpointProposal


AGENT_MODEL = "google:gemini-3.1-flash-lite"
AGENT_RETRIES: AgentRetries = {"output": 4}


class OrderedCheckpoint(BaseModel):
    title: str = Field(min_length=1)
    reasoning: str = Field(min_length=1, max_length=240)


class RoutePlanOutput(BaseModel):
    ordered_checkpoints: list[OrderedCheckpoint] = Field(min_length=1)
    narrative_arc: str = Field(min_length=1, max_length=600)


@dataclass
class RoutePlannerDeps:
    checkpoints: list[CheckpointProposal]


# TODO: Give the agent better spatial context once the simple title-ordering
# flow works. Possible approaches:
# - Provide a rendered map image with checkpoint pins.
# - Provide a distance matrix between all selected checkpoints.
# - Provide pairwise walking times/distances from a routing provider.
# - Provide a rough route preview or route feasibility summary.
# - Add a route critic agent that rejects routes that look awkward, inefficient or narratively weak.
route_planner_agent = Agent[
    RoutePlannerDeps,
    RoutePlanOutput,
](
    model=AGENT_MODEL,
    name="route_planner_agent",
    deps_type=RoutePlannerDeps,
    output_type=RoutePlanOutput,
    retries=AGENT_RETRIES,
    defer_model_check=True,
    instructions="""
You order selected walking-tour checkpoints.

Return every selected checkpoint exactly once. Each ordered checkpoint must
include the checkpoint title copied exactly from the provided checkpoint.title
value and brief reasoning for that position. Include a concise narrative arc for
the overall tour.
""".strip(),
)


@route_planner_agent.instructions
def add_selected_checkpoints_instruction(ctx: RunContext[RoutePlannerDeps]) -> str:
    checkpoint_lines = [f"- {checkpoint.title}: {checkpoint.brief_description}" for checkpoint in ctx.deps.checkpoints]
    return "Selected checkpoints to order:\n" + "\n".join(checkpoint_lines)


@route_planner_agent.output_validator
def validate_route_plan(
    ctx: RunContext[RoutePlannerDeps],
    output: RoutePlanOutput,
) -> RoutePlanOutput:
    input_titles = [checkpoint.title for checkpoint in ctx.deps.checkpoints]
    output_titles = [checkpoint.title for checkpoint in output.ordered_checkpoints]

    if Counter(output_titles) != Counter(input_titles):
        raise ModelRetry(
            "Invalid checkpoint titles in route plan. "
            f"Expected titles: {input_titles}. "
            f"Model returned titles: {output_titles}. "
            "Return every expected title exactly once and do not add extra titles."
        )

    return output
