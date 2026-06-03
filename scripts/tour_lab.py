from __future__ import annotations

import html
import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

os.environ.setdefault("GRADIO_ANALYTICS_ENABLED", "False")

import gradio as gr
from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))
load_dotenv()

try:
    from tour_gen.tts.gemini import GEMINI_TTS_VOICE
except Exception:
    GEMINI_TTS_VOICE = "Kore"


DEFAULT_LOCATION = "Wandsworth Common, southwest London"
DEFAULT_PROMPT = (
    "Create a walking tour of Wandsworth Common in southwest London, focused "
    "on how the common has changed through the years and evolved alongside "
    "London into its present-day form. Include 8-10 real, visitable locations "
    "around the common and nearby streets, using each stop to reveal a layer "
    "of the area's history: common land, Victorian preservation, railway and "
    "suburban growth, wartime use, civic life, and modern conservation. Also "
    "give strong attention to the nature of the common today, including its "
    "ponds, grassland, trees, habitats, seasonal character, and wildlife."
)
TOURS_DIR = PROJECT_ROOT / "data" / "tours"

GeocoderName = Literal["Mapbox", "Google Maps"]


@dataclass
class DraftTour:
    prompt: str
    location: str
    voice_style: str | None
    checkpoint_research: Any
    checkpoint_coordinates: list[Any]
    route_plan: Any
    chapters: Any


async def generate_draft(
    location: str,
    prompt: str,
    voice_style: str,
    geocoder_name: GeocoderName,
) -> tuple[
    DraftTour | None,
    str,
    dict[str, Any] | None,
    dict[str, Any] | None,
    dict[str, Any] | None,
    list[dict[str, Any]],
    str,
]:
    if not location.strip() or not prompt.strip():
        return None, "Enter a location and prompt.", None, None, None, [], ""

    try:
        from tour_gen.pipeline import (
            plan_route,
            research_checkpoints,
            write_chapters,
        )

        geocoder = _geocoder(geocoder_name)
        checkpoint_research, checkpoint_coordinates = await research_checkpoints(
            prompt,
            location=location,
            geocoder=geocoder,
        )
        route_plan = await plan_route(checkpoint_research)
        chapters = await write_chapters(
            route_plan,
            voice_style=voice_style.strip() or None,
        )
    except Exception as exc:
        return None, _error_message(exc), None, None, None, [], ""

    draft = DraftTour(
        prompt=prompt,
        location=location,
        voice_style=voice_style.strip() or None,
        checkpoint_research=checkpoint_research,
        checkpoint_coordinates=checkpoint_coordinates,
        route_plan=route_plan,
        chapters=chapters,
    )
    return (
        draft,
        f"Draft ready: {chapters.tour_title}",
        checkpoint_research.model_dump(mode="json"),
        route_plan.model_dump(mode="json"),
        chapters.model_dump(mode="json"),
        _coordinates_json(checkpoint_coordinates),
        _map_html(checkpoint_coordinates),
    )


async def approve_draft(
    draft: DraftTour | None,
    voice: str,
    audio_format: str,
) -> tuple[str, dict[str, str] | None]:
    if draft is None:
        return "Generate a draft before approving.", None

    try:
        from tour_gen.pipeline import narrate_tour
        from tour_gen.tts.gemini import GeminiTTSProvider

        narration = await narrate_tour(
            draft.chapters,
            tts_provider=GeminiTTSProvider(),
            voice=voice.strip() or GEMINI_TTS_VOICE,
            audio_format=audio_format,
        )
        saved_paths = _persist_tour(
            draft,
            narration=narration,
            voice=voice.strip() or GEMINI_TTS_VOICE,
            generated_at=datetime.now(),
        )
    except Exception as exc:
        return _error_message(exc), None

    return "Tour narrated and persisted.", saved_paths


def build_app() -> gr.Blocks:
    with gr.Blocks(title="Tour Lab") as app:
        gr.Markdown("# Tour Lab")
        draft_state = gr.State(value=None)

        with gr.Row():
            geocoder = gr.Radio(
                ["Mapbox", "Google Maps"],
                value="Mapbox",
                label="Geocoder",
            )
            voice = gr.Textbox(value=GEMINI_TTS_VOICE, label="Voice")
            audio_format = gr.Radio(["wav"], value="wav", label="Audio format")

        location = gr.Textbox(value=DEFAULT_LOCATION, label="Location")
        prompt = gr.Textbox(value=DEFAULT_PROMPT, lines=7, label="Prompt")
        voice_style = gr.Textbox(lines=3, label="Voice style")

        with gr.Row():
            generate = gr.Button("Generate draft", variant="primary")
            approve = gr.Button("Approve, narrate, and persist", variant="primary")

        status = gr.Textbox(label="Status", interactive=False)
        saved_paths = gr.JSON(label="Saved paths")
        map_view = gr.HTML(label="Map")

        with gr.Accordion("Checkpoint coordinates", open=True):
            coordinates = gr.JSON()
        with gr.Row():
            checkpoint_research = gr.JSON(label="Checkpoint research")
            route_plan = gr.JSON(label="Route plan")
        chapters = gr.JSON(label="Chapters")

        generate.click(
            fn=generate_draft,
            inputs=[location, prompt, voice_style, geocoder],
            outputs=[
                draft_state,
                status,
                checkpoint_research,
                route_plan,
                chapters,
                coordinates,
                map_view,
            ],
        )
        approve.click(
            fn=approve_draft,
            inputs=[draft_state, voice, audio_format],
            outputs=[status, saved_paths],
        )

    return app


def _geocoder(name: GeocoderName) -> Any:
    if name == "Google Maps":
        from tour_gen.geo.geoencode.google_maps import GoogleMapsGeocoder

        return GoogleMapsGeocoder()
    from tour_gen.geo.geoencode.mapbox import MapboxGeocoder

    return MapboxGeocoder()


def _persist_tour(
    draft: DraftTour,
    *,
    narration: Any,
    voice: str,
    generated_at: datetime,
) -> dict[str, str]:
    from tour_gen.pipeline import TourGenerationOutput
    from tour_gen.tour_artifacts import (
        tour_artifact_to_frontend,
        tour_output_to_artifact,
    )

    output = TourGenerationOutput(
        checkpoint_research=draft.checkpoint_research,
        checkpoint_coordinates=draft.checkpoint_coordinates,
        route_plan=draft.route_plan,
        chapters=draft.chapters,
        narration=narration,
    )
    artifact = tour_output_to_artifact(
        output,
        prompt=draft.prompt,
        location=draft.location,
        voice=voice,
        generated_at=generated_at,
    )

    tour_files_dir = TOURS_DIR / artifact.metadata.id
    tour_files_dir.mkdir(parents=True, exist_ok=True)
    _write_audio_files(narration.chapters, artifact, tour_files_dir)

    artifact_path = tour_files_dir / "tour_artifact.json"
    _write_json(artifact_path, artifact.model_dump(mode="json"))

    frontend_tour = tour_artifact_to_frontend(artifact)
    frontend_path = tour_files_dir / "frontend_tour.json"
    _write_json(frontend_path, frontend_tour.model_dump(mode="json"))

    return {
        "tour_files_dir": str(tour_files_dir),
        "artifact_path": str(artifact_path),
        "frontend_path": str(frontend_path),
    }


def _write_audio_files(
    narrated_chapters: list[Any],
    artifact: Any,
    output_dir: Path,
) -> None:
    for source_chapter, artifact_chapter in zip(
        narrated_chapters,
        artifact.narration.chapters,
        strict=True,
    ):
        audio_path = output_dir / artifact_chapter.audio.src
        audio_path.write_bytes(source_chapter.audio)


def _write_json(path: Path, data: Any) -> None:
    path.write_text(
        json.dumps(data, indent=2) + "\n",
        encoding="utf-8",
    )


def _coordinates_json(
    checkpoint_coordinates: list[Any],
) -> list[dict[str, Any]]:
    return [
        {
            "title": coordinate.title,
            "lat": coordinate.lat,
            "lon": coordinate.lon,
            "formatted_address": coordinate.formatted_address,
            "distance_tool_place_name": coordinate.distance_tool_place_name,
        }
        for coordinate in checkpoint_coordinates
    ]


def _map_html(checkpoint_coordinates: list[Any]) -> str:
    if not checkpoint_coordinates:
        return "<p>No checkpoint coordinates.</p>"

    center_lat = sum(point.lat for point in checkpoint_coordinates) / len(
        checkpoint_coordinates
    )
    center_lon = sum(point.lon for point in checkpoint_coordinates) / len(
        checkpoint_coordinates
    )
    markers = [
        {
            "title": point.title,
            "lat": point.lat,
            "lon": point.lon,
        }
        for point in checkpoint_coordinates
    ]
    srcdoc = f"""
<!doctype html>
<html>
  <head>
    <meta charset="utf-8" />
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <style>html, body, #map {{ height: 100%; margin: 0; }}</style>
  </head>
  <body>
    <div id="map"></div>
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <script>
      const markers = {json.dumps(markers)};
      const map = L.map("map").setView([{center_lat}, {center_lon}], 15);
      L.tileLayer("https://tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png", {{
        maxZoom: 19,
        attribution: "&copy; OpenStreetMap"
      }}).addTo(map);
      const bounds = [];
      markers.forEach((marker, index) => {{
        const latLng = [marker.lat, marker.lon];
        bounds.push(latLng);
        L.marker(latLng).addTo(map).bindPopup(`${{index + 1}}. ${{marker.title}}`);
      }});
      if (bounds.length > 1) {{
        map.fitBounds(bounds, {{ padding: [30, 30] }});
      }}
    </script>
  </body>
</html>
"""
    return (
        '<iframe title="Checkpoint map" '
        'style="width: 100%; height: 460px; border: 1px solid #ddd;" '
        f'srcdoc="{html.escape(srcdoc, quote=True)}"></iframe>'
    )


def _error_message(exc: Exception) -> str:
    return f"{type(exc).__name__}: {exc}"


if __name__ == "__main__":
    build_app().queue().launch(
        server_name="127.0.0.1",
        server_port=int(os.environ.get("TOUR_LAB_PORT", "7861")),
    )
