from pydantic_ai import Agent, AgentRetries
from pydantic_ai.capabilities.web_search import WebSearch

from tour_gen.agents.tour_assistant.instructions import (
    add_tour_context_instruction,
)
from tour_gen.agents.tour_assistant.models import TourAssistantDeps
from tour_gen.agents.tour_assistant.validation import (
    MAX_RESPONSE_WORDS,
    validate_response_length,
)


AGENT_MODEL = "google:gemini-3.1-flash-lite"
AGENT_RETRIES: AgentRetries = {"output": 3}


WEB_SEARCH: WebSearch[TourAssistantDeps] = WebSearch(
    search_context_size="medium",
    max_uses=4,
)


TOUR_ASSISTANT_INSTRUCTIONS = f"""
You are a concise, knowledgeable companion for a walking tour that the user is
currently viewing and listening to.

Answer questions using the supplied tour and chapter context. Interpret words
such as "this", "here", "that", and "just now" using the selected chapter and
the approximate playback position. Do not pretend that approximate playback
progress provides exact word-level timing.

Use web search when the user asks for current information or information that
is not supported by the stored tour. Make it clear when current web information
and the stored tour differ. Never invent places, facts, or live conditions.

Return only the answer for the user. Keep it natural to read while walking and
no longer than {MAX_RESPONSE_WORDS} words. Do not offer to control the app or
claim that you changed playback, the route, or the selected chapter.
""".strip()


tour_assistant_agent = Agent[TourAssistantDeps, str](
    model=AGENT_MODEL,
    name="tour_assistant_agent",
    deps_type=TourAssistantDeps,
    output_type=str,
    retries=AGENT_RETRIES,
    defer_model_check=True,
    capabilities=[WEB_SEARCH],
    instructions=TOUR_ASSISTANT_INSTRUCTIONS,
)

tour_assistant_agent.instructions(add_tour_context_instruction)
tour_assistant_agent.output_validator(validate_response_length)
