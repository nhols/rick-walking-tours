from uuid import UUID

from supabase import Client


class SupabaseAudioStore:
    def __init__(self, client: Client) -> None:
        self.bucket = client.storage.from_("tour-audio")

    def save(
        self,
        *,
        owner_id: UUID,
        tour_id: UUID,
        position: int,
        audio_format: str,
        media_type: str,
        audio: bytes,
    ) -> str:
        extension = audio_format.lower().strip().lstrip(".")
        if not extension.isalnum():
            raise ValueError(f"Invalid audio format: {audio_format!r}")
        path = f"{owner_id}/{tour_id}/{position:03d}.{extension}"
        self.bucket.upload(
            path,
            audio,
            {"content-type": media_type, "upsert": "true"},
        )
        return path
