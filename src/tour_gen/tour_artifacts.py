import hashlib
import re
from datetime import datetime

from pydantic import BaseModel, Field

from tour_gen.agents.chapter_writer import ChapterWriterOutput, TTSStyle
from tour_gen.agents.checkpoint_researcher import CheckpointResearchOutput
from tour_gen.agents.route_planner import RoutePlanOutput
from tour_gen.pipeline import CheckpointCoordinates, TourGenerationOutput


class TourArtifactMetadata(BaseModel):
    id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    prompt: str = Field(min_length=1)
    location: str = Field(min_length=1)
    generated_at: datetime
    voice: str = Field(min_length=1)


class TourAudioAsset(BaseModel):
    src: str = Field(min_length=1)
    media_type: str = Field(min_length=1)
    audio_format: str = Field(min_length=1)
    byte_count: int = Field(ge=0)
    voice: str = Field(min_length=1)
    model: str | None = None
    duration_seconds: float | None = None


class TourArtifactNarratedChapter(BaseModel):
    title: str = Field(min_length=1)
    narration: str = Field(min_length=1)
    audio: TourAudioAsset


class TourArtifactNarration(BaseModel):
    chapters: list[TourArtifactNarratedChapter] = Field(min_length=1)


class TourArtifact(BaseModel):
    metadata: TourArtifactMetadata
    checkpoint_research: CheckpointResearchOutput
    checkpoint_coordinates: list[CheckpointCoordinates]
    route_plan: RoutePlanOutput
    chapters: ChapterWriterOutput
    narration: TourArtifactNarration


class FrontendPosition(BaseModel):
    lat: float
    lon: float


class FrontendMapBounds(BaseModel):
    southWest: FrontendPosition
    northEast: FrontendPosition


class FrontendMap(BaseModel):
    center: FrontendPosition
    bounds: FrontendMapBounds


class FrontendAudio(BaseModel):
    src: str = Field(min_length=1)
    mediaType: str = Field(min_length=1)
    format: str = Field(min_length=1)
    byteCount: int = Field(ge=0)
    voice: str = Field(min_length=1)
    model: str | None = None
    durationSeconds: float | None = None


class FrontendTourStop(BaseModel):
    id: str = Field(min_length=1)
    order: int = Field(ge=1)
    title: str = Field(min_length=1)
    description: str = Field(min_length=1)
    routeReasoning: str = Field(min_length=1)
    position: FrontendPosition
    formattedAddress: str | None = None
    distanceToolPlaceName: str = Field(min_length=1)
    narration: str = Field(min_length=1)
    audio: FrontendAudio


class FrontendTour(BaseModel):
    id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    location: str = Field(min_length=1)
    generatedAt: datetime
    narrativeArc: str = Field(min_length=1)
    ttsStyle: TTSStyle
    map: FrontendMap
    stops: list[FrontendTourStop] = Field(min_length=1)


def tour_output_to_artifact(
    output: TourGenerationOutput,
    *,
    prompt: str,
    location: str,
    voice: str,
    generated_at: datetime | None = None,
) -> TourArtifact:
    generated_at = generated_at or datetime.now()
    narration_chapters = [
        TourArtifactNarratedChapter(
            title=chapter.title,
            narration=chapter.narration,
            audio=TourAudioAsset(
                src=audio_filename(index, chapter.title, chapter.audio_format),
                media_type=chapter.media_type,
                audio_format=chapter.audio_format,
                byte_count=len(chapter.audio),
                voice=chapter.voice,
                model=chapter.model,
                duration_seconds=chapter.duration_seconds,
            ),
        )
        for index, chapter in enumerate(output.narration.chapters, start=1)
    ]

    return TourArtifact(
        metadata=TourArtifactMetadata(
            id=slugify(location),
            title=output.chapters.tour_title,
            prompt=prompt,
            location=location,
            generated_at=generated_at,
            voice=voice,
        ),
        checkpoint_research=output.checkpoint_research,
        checkpoint_coordinates=output.checkpoint_coordinates,
        route_plan=output.route_plan,
        chapters=output.chapters,
        narration=TourArtifactNarration(chapters=narration_chapters),
    )


def tour_artifact_to_frontend(artifact: TourArtifact) -> FrontendTour:
    proposals_by_title = _index_by_title(
        artifact.checkpoint_research.proposals,
        "checkpoint proposal",
    )
    coordinates_by_title = _index_by_title(
        artifact.checkpoint_coordinates,
        "checkpoint coordinates",
    )
    chapters_by_title = _index_by_title(
        artifact.chapters.chapters,
        "chapter",
    )
    narration_by_title = _index_by_title(
        artifact.narration.chapters,
        "narration",
    )

    stops: list[FrontendTourStop] = []
    for order, ordered_checkpoint in enumerate(
        artifact.route_plan.ordered_checkpoints,
        start=1,
    ):
        title = ordered_checkpoint.title
        proposal = _required_lookup(proposals_by_title, title, "checkpoint proposal")
        coordinates = _required_lookup(
            coordinates_by_title,
            title,
            "checkpoint coordinates",
        )
        chapter = _required_lookup(chapters_by_title, title, "chapter")
        narration = _required_lookup(narration_by_title, title, "narration")

        stops.append(
            FrontendTourStop(
                id=f"{order:02d}-{slugify(title)}",
                order=order,
                title=title,
                description=proposal.brief_description,
                routeReasoning=ordered_checkpoint.reasoning,
                position=FrontendPosition(
                    lat=coordinates.lat,
                    lon=coordinates.lon,
                ),
                formattedAddress=coordinates.formatted_address,
                distanceToolPlaceName=proposal.distance_tool_place_name,
                narration=strip_audio_tags(chapter.narration),
                audio=_frontend_audio(narration.audio),
            )
        )

    return FrontendTour(
        id=artifact.metadata.id,
        title=artifact.metadata.title,
        location=artifact.metadata.location,
        generatedAt=artifact.metadata.generated_at,
        narrativeArc=artifact.route_plan.narrative_arc,
        ttsStyle=artifact.chapters.tts_style,
        map=_frontend_map(stops),
        stops=stops,
    )


def audio_filename(index: int, title: str, audio_format: str) -> str:
    return f"{index:02d}-{slugify(title)}.{audio_format}"


def slugify(value: str, max_length: int = 80) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower()).strip("-")
    slug = slug or "tour"
    if len(slug) <= max_length:
        return slug

    digest = hashlib.sha1(slug.encode("utf-8")).hexdigest()[:8]
    suffix = f"-{digest}"
    prefix = slug[: max_length - len(suffix)].rstrip("-")
    return f"{prefix}{suffix}"


def strip_audio_tags(narration: str) -> str:
    """Remove bracketed audio/performance tags, e.g. "[softly] hello" -> "hello"."""
    return re.sub(r"\[.*?\]\s*", "", narration).strip()


def _frontend_audio(audio: TourAudioAsset) -> FrontendAudio:
    return FrontendAudio(
        src=audio.src,
        mediaType=audio.media_type,
        format=audio.audio_format,
        byteCount=audio.byte_count,
        voice=audio.voice,
        model=audio.model,
        durationSeconds=audio.duration_seconds,
    )


def _frontend_map(stops: list[FrontendTourStop]) -> FrontendMap:
    lats = [stop.position.lat for stop in stops]
    lons = [stop.position.lon for stop in stops]
    return FrontendMap(
        center=FrontendPosition(
            lat=sum(lats) / len(lats),
            lon=sum(lons) / len(lons),
        ),
        bounds=FrontendMapBounds(
            southWest=FrontendPosition(
                lat=min(lats),
                lon=min(lons),
            ),
            northEast=FrontendPosition(
                lat=max(lats),
                lon=max(lons),
            ),
        ),
    )


def _index_by_title[T](
    items: list[T],
    label: str,
) -> dict[str, T]:
    indexed: dict[str, T] = {}
    for item in items:
        title = getattr(item, "title")
        if title in indexed:
            raise ValueError(f"Duplicate {label} title: {title}")
        indexed[title] = item
    return indexed


def _required_lookup[T](
    indexed: dict[str, T],
    title: str,
    label: str,
) -> T:
    try:
        return indexed[title]
    except KeyError as exc:
        raise ValueError(f"Missing {label} for ordered checkpoint: {title}") from exc
