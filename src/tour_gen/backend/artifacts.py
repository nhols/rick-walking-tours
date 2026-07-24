from typing import Protocol
from uuid import UUID

from supabase import Client


TOUR_AUDIO_BUCKET = "tour-audio"


class ArtifactStore(Protocol):
    def save_audio(
        self,
        *,
        owner_id: UUID,
        tour_id: UUID,
        position: int,
        audio_format: str,
        media_type: str,
        audio: bytes,
    ) -> str: ...

    def create_signed_url(self, path: str, *, expires_in: int = 3_600) -> str: ...


class SupabaseArtifactStore:
    def __init__(self, client: Client, *, bucket: str = TOUR_AUDIO_BUCKET) -> None:
        self.bucket = client.storage.from_(bucket)

    def save_audio(
        self,
        *,
        owner_id: UUID,
        tour_id: UUID,
        position: int,
        audio_format: str,
        media_type: str,
        audio: bytes,
    ) -> str:
        extension = _safe_extension(audio_format)
        path = f"{owner_id}/{tour_id}/{position:03d}.{extension}"
        self.bucket.upload(
            path,
            audio,
            {"content-type": media_type, "upsert": "true"},
        )
        return path

    def create_signed_url(self, path: str, *, expires_in: int = 3_600) -> str:
        response = self.bucket.create_signed_url(path, expires_in)
        url = response.get("signedURL") or response.get("signedUrl")
        if not url:
            raise RuntimeError("Supabase Storage did not return a signed URL")
        return url


def _safe_extension(value: str) -> str:
    extension = value.lower().strip().lstrip(".")
    if not extension or not extension.isalnum():
        raise ValueError(f"Invalid audio format: {value!r}")
    return extension
