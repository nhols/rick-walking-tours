from pydantic_ai import RunContext

from tour_gen.agents.tour_assistant.models import TourAssistantDeps
from tour_gen.backend.models import TourChapter
from tour_gen.geo.routes import WalkingRoute


def add_tour_context_instruction(ctx: RunContext[TourAssistantDeps]) -> str:
    deps = ctx.deps
    context = deps.load_context()
    chapters = sorted(context.output.chapters, key=lambda chapter: chapter.position)
    duration = context.selected_chapter.duration_seconds
    progress = (
        min(deps.chapter_playback_seconds / duration, 1.0)
        if duration is not None
        else None
    )
    tour_title = context.tour.title or context.tour.input.location
    return (
        "Use this server-loaded tour as the source of truth for the conversation. "
        "The selected chapter is both the chapter shown in the UI and the chapter "
        "being played. Playback progress is approximate because word-level audio "
        "timestamps are unavailable.\n\n"
        "TOUR\n"
        f"Title: {tour_title}\n"
        f"Location: {context.tour.input.location}\n\n"
        "ORDERED CHECKPOINTS\n"
        f"{_format_chapters(chapters)}\n\n"
        "WALKING ROUTE\n"
        f"{_format_route(context.approved_plan.payload.route, chapters)}\n\n"
        "CURRENT UI STATE\n"
        f"Selected chapter: Stop {context.selected_chapter.position} — "
        f"{context.selected_chapter.title}\n"
        f"{_format_playback(deps.chapter_playback_seconds, duration, progress)}"
    )


def _format_chapters(chapters: list[TourChapter]) -> str:
    return "\n\n".join(
        f"Stop {chapter.position} — {chapter.title}\n"
        f"Narration:\n{chapter.narration}"
        for chapter in chapters
    )


def _format_route(
    route: WalkingRoute | None,
    chapters: list[TourChapter],
) -> str:
    if route is None:
        return "No walking route is stored for this tour."

    lines = []
    for index, leg in enumerate(route.legs):
        if index + 1 >= len(chapters):
            break
        start = chapters[index]
        end = chapters[index + 1]
        lines.append(
            f"Stop {start.position} — {start.title} → "
            f"Stop {end.position} — {end.title}: "
            f"{_format_distance(leg.distance_meters)}, "
            f"{_format_minutes(leg.duration_seconds)}"
        )

    if not lines:
        lines.append("Per-stop walking times are unavailable.")
    lines.append(
        "Total walking route: "
        f"{_format_distance(route.distance_meters)}, "
        f"{_format_minutes(route.duration_seconds)}"
    )
    return "\n".join(lines)


def _format_playback(
    playback_seconds: float,
    duration_seconds: float | None,
    progress: float | None,
) -> str:
    playback = _format_clock(playback_seconds)
    if duration_seconds is None or progress is None:
        return f"Playback: {playback}; chapter duration unavailable."
    return (
        f"Playback: {playback} of {_format_clock(duration_seconds)} "
        f"({progress * 100:.1f}%, approximate)."
    )


def _format_distance(meters: float) -> str:
    if meters < 1_000:
        return f"{round(meters)} m"
    return f"{meters / 1_000:.1f} km"


def _format_minutes(seconds: float) -> str:
    minutes = max(1, round(seconds / 60))
    return f"{minutes} min"


def _format_clock(seconds: float) -> str:
    total_seconds = round(seconds)
    minutes, remaining_seconds = divmod(total_seconds, 60)
    return f"{minutes}:{remaining_seconds:02d}"
