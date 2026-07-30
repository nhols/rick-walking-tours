from pydantic_ai import ModelRetry, RunContext

from tour_gen.agents.tour_assistant.models import TourAssistantDeps


MAX_RESPONSE_WORDS = 180


def validate_response_length(
    _ctx: RunContext[TourAssistantDeps],
    output: str,
) -> str:
    response = output.strip()
    if not response:
        raise ModelRetry("Return a helpful, non-empty answer.")

    word_count = len(response.split())
    if word_count > MAX_RESPONSE_WORDS:
        raise ModelRetry(
            "Your answer is too long. "
            f"Return no more than {MAX_RESPONSE_WORDS} words; "
            f"the previous answer contained {word_count} words."
        )
    return response
