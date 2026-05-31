import base64
import io
import os
import wave

from google import genai
from google.genai import types

from tour_gen.agents.chapter_writer import TTSStyle
from tour_gen.tts.provider import TTSProvider, TTSRequest, TTSResult


GEMINI_TTS_MODEL = "gemini-3.1-flash-tts-preview"
GEMINI_TTS_VOICE = "Kore"
PCM_SAMPLE_RATE = 24_000
PCM_CHANNELS = 1
PCM_SAMPLE_WIDTH = 2


class GeminiTTSProvider(TTSProvider):
    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str = GEMINI_TTS_MODEL,
        voice: str = GEMINI_TTS_VOICE,
    ) -> None:
        self.model = model
        self.voice = voice
        self.client = genai.Client(
            api_key=api_key
            or os.environ.get("GOOGLE_API_KEY")
            or os.environ.get("GEMINI_API_KEY")
        )

    async def synthesize(self, request: TTSRequest) -> TTSResult:
        model = request.model or self.model
        voice = request.voice or self.voice
        prompt = _build_tts_prompt(request.text, request.tts_style, request.instructions)

        response = await self.client.aio.models.generate_content(
            model=model,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_modalities=["AUDIO"],
                speech_config=types.SpeechConfig(
                    voice_config=types.VoiceConfig(
                        prebuilt_voice_config=types.PrebuiltVoiceConfig(
                            voice_name=voice,
                        )
                    )
                ),
            ),
        )

        inline_data = response.candidates[0].content.parts[0].inline_data
        pcm_audio = _decode_audio_data(inline_data.data)
        wav_audio = _pcm_to_wav(pcm_audio)

        return TTSResult(
            audio=wav_audio,
            media_type="audio/wav",
            audio_format="wav",
            voice=voice,
            model=model,
            provider_metadata={
                "provider": "gemini",
                "source_media_type": inline_data.mime_type,
            },
        )


def _build_tts_prompt(
    text: str,
    tts_style: TTSStyle | None,
    instructions: str | None,
) -> str:
    parts = [
        "Read the following walking-tour chapter exactly as written.",
        "Preserve square-bracket performance tags such as [brief pause] or [softly].",
    ]

    if tts_style is not None:
        parts.extend(
            [
                f"Scene setting: {tts_style.scene_setting}",
                f"Tone: {tts_style.tone}",
                f"Pace: {tts_style.pace}",
            ]
        )
        if tts_style.accent:
            parts.append(f"Accent: {tts_style.accent}")
        if tts_style.performance_notes:
            parts.append("Performance notes: " + "; ".join(tts_style.performance_notes))

    if instructions:
        parts.append(f"Additional instructions: {instructions}")

    parts.append(f"Narration:\n{text}")
    return "\n\n".join(parts)


def _decode_audio_data(data: bytes | str) -> bytes:
    if isinstance(data, str):
        return base64.b64decode(data)
    return data


def _pcm_to_wav(
    pcm: bytes,
    *,
    channels: int = PCM_CHANNELS,
    rate: int = PCM_SAMPLE_RATE,
    sample_width: int = PCM_SAMPLE_WIDTH,
) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav:
        wav.setnchannels(channels)
        wav.setframerate(rate)
        wav.setsampwidth(sample_width)
        wav.writeframes(pcm)
    return buffer.getvalue()
