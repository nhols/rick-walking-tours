from pydantic_ai import Agent, AgentRetries
from pydantic_ai.capabilities.web_search import WebSearch

from tour_gen.agents.chapter_writer.models import (
    ChapterWriterDeps,
    ChapterWriterOutput,
)
from tour_gen.agents.chapter_writer.instructions import add_plan_instruction
from tour_gen.agents.chapter_writer.validation import (
    validate_chapters,
)


AGENT_MODEL = "google:gemini-3.1-flash-lite"
AGENT_RETRIES: AgentRetries = {"output": 4}


WEB_SEARCH: WebSearch[ChapterWriterDeps] = WebSearch(
    search_context_size="high",
    max_uses=12,
)


CHAPTER_WRITER_INSTRUCTIONS = """
You write narration chapters for an ordered walking-tour route.

Use web search to enrich each chapter with grounded details, little facts,
useful recommendations, and interesting online research. Prefer specific
details over generic description.

Each checkpoint includes an exact physical place selected and geocoded during
research. Write about that exact place. Never silently replace it with another
venue, landmark, branch, or similarly themed attraction. If web results are
ambiguous, keep the supplied place identity and avoid unsupported details.

Return a concise tour_title for the full tour, with no more than 8 words.
The tour_title should be polished and specific enough to display in the app.

Return one chapter for every ordered checkpoint. Each chapter title must be
copied exactly from the provided checkpoint title. Write narration that is
designed to be spoken aloud. Each narration should be around 200-1000 words,
roughly 1-5 minutes of speech.

Return one tour-level tts_style for the full audio tour.

The tts_style should match any user-provided voice style guide first and
foremost. Treat that guide as the source of truth for tone, accent, pacing,
energy, delivery, and performance preferences. If the user voice style guide is
not provided, or if it leaves gaps, fill those gaps using the tour's topic,
location, audience, and narrative arc. For example, an Edinburgh Harry Potter
tour would usually suit a British narration style unless the user asks for
something else.

You may use square-bracket performance tags sparingly inside narration where
they improve the spoken result, for example [softly], [brief pause], or
[with a smile]. Do not overuse them.

The narration field must contain only the exact words and performance tags to
be spoken by TTS. Do not include citations, reference markers, footnotes, URLs,
source IDs, bibliographies, markdown links, or anything else that is not
narration. For example, never write reference markers like [1.28],
[1.7, 1.26], or [source] in narration.
""".strip()


chapter_writer_agent = Agent[
    ChapterWriterDeps,
    ChapterWriterOutput,
](
    model=AGENT_MODEL,
    name="chapter_writer_agent",
    deps_type=ChapterWriterDeps,
    output_type=ChapterWriterOutput,
    retries=AGENT_RETRIES,
    defer_model_check=True,
    capabilities=[WEB_SEARCH],
    instructions=CHAPTER_WRITER_INSTRUCTIONS,
)

chapter_writer_agent.instructions(add_plan_instruction)
chapter_writer_agent.output_validator(validate_chapters)
