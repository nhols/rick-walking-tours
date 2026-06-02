import asyncio
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from tour_gen.geo.geoencode.mapbox import MapboxGeocoder
from tour_gen.pipeline import generate_tour
from tour_gen.tour_artifacts import (
    TourArtifact,
    tour_artifact_to_frontend,
    tour_output_to_artifact,
)
from tour_gen.tts.narration import NarratedChapter
from tour_gen.tts.gemini import GEMINI_TTS_VOICE, GeminiTTSProvider


DEFAULT_PROMPT = "Harry Potter themed walking tour in Edinburgh"
DEFAULT_LOCATION = "Edinburgh"
DEFAULT_VOICE_STYLE = None
DATA_DIR = PROJECT_ROOT / "data"
logger = logging.getLogger(__name__)


async def main() -> None:
    generated_at = datetime.now()
    output_dir = DATA_DIR / f"tour_{generated_at.strftime('%Y%m%d_%H%M%S')}"
    output_dir.mkdir(parents=True, exist_ok=True)

    logger.info(
        "Generating tour prompt=%s location=%s output_dir=%s",
        DEFAULT_PROMPT,
        DEFAULT_LOCATION,
        output_dir,
    )

    pipeline_output = await generate_tour(
        DEFAULT_PROMPT,
        location=DEFAULT_LOCATION,
        geocoder=MapboxGeocoder(),
        tts_provider=GeminiTTSProvider(),
        voice=GEMINI_TTS_VOICE,
        voice_style=DEFAULT_VOICE_STYLE,
        audio_format="wav",
    )

    artifact = tour_output_to_artifact(
        pipeline_output,
        prompt=DEFAULT_PROMPT,
        location=DEFAULT_LOCATION,
        voice=GEMINI_TTS_VOICE,
        generated_at=generated_at,
    )
    write_audio_files(pipeline_output.narration.chapters, artifact, output_dir)

    artifact_path = output_dir / "tour_artifact.json"
    write_json(artifact_path, artifact.model_dump(mode="json"))

    frontend_tour = tour_artifact_to_frontend(artifact)
    frontend_path = output_dir / "frontend_tour.json"
    write_json(frontend_path, frontend_tour.model_dump(mode="json"))

    logger.info(
        "Tour files written artifact_path=%s frontend_path=%s",
        artifact_path,
        frontend_path,
    )
    print(
        json.dumps(
            {
                "output_dir": str(output_dir),
                "artifact_path": str(artifact_path),
                "frontend_path": str(frontend_path),
            },
            indent=2,
        )
    )


def write_audio_files(
    narrated_chapters: list[NarratedChapter],
    artifact: TourArtifact,
    output_dir: Path,
) -> None:
    for source_chapter, artifact_chapter in zip(
        narrated_chapters,
        artifact.narration.chapters,
        strict=True,
    ):
        audio_path = output_dir / artifact_chapter.audio.src
        audio_path.write_bytes(source_chapter.audio)
        logger.info(
            "Wrote chapter audio title=%s output_path=%s bytes=%s",
            artifact_chapter.title,
            audio_path,
            artifact_chapter.audio.byte_count,
        )


def write_json(path: Path, data: Any) -> None:
    path.write_text(
        json.dumps(data, indent=2) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    asyncio.run(main())
