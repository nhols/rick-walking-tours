from uuid import UUID, uuid4

from tour_gen import pipeline
from tour_gen.agents.chapter_writer import Chapter, ChapterWriterOutput, TTSStyle
from tour_gen.agents.checkpoint_researcher import (
    CheckpointProposal,
    CheckpointResearchOutput,
)
from tour_gen.backend.models import (
    TourChapter,
    TourInput,
    TourOutputPayload,
    TourPlanPayload,
)
from tour_gen.backend.ports import AudioStore, WrittenTour
from tour_gen.tts.provider import TTSProvider


class AgentTourProducer:
    def __init__(self, tts: TTSProvider, audio: AudioStore) -> None:
        self.tts = tts
        self.audio = audio

    async def write(self, input: TourInput, plan: TourPlanPayload) -> WrittenTour:
        written = await pipeline.write_chapters(
            plan=_agent_plan(plan),
            location=input.location,
            voice_style=input.voice_style,
        )
        checkpoints = {item.title: item for item in plan.checkpoints}
        chapters: list[TourChapter] = []
        for position, chapter in enumerate(written.chapters, start=1):
            checkpoint = checkpoints.get(chapter.title)
            if checkpoint is None:
                raise ValueError(f"Chapter has no checkpoint: {chapter.title}")
            chapters.append(
                TourChapter(
                    id=uuid4(),
                    checkpoint_id=checkpoint.id,
                    position=position,
                    title=chapter.title,
                    narration=chapter.narration,
                )
            )
        return WrittenTour(
            title=written.tour_title,
            output=TourOutputPayload(
                tts_style=written.tts_style.model_dump(mode="json"),
                chapters=chapters,
            ),
        )

    async def narrate(
        self,
        owner_id: UUID,
        tour_id: UUID,
        input: TourInput,
        written: WrittenTour,
    ) -> TourOutputPayload:
        chapters = ChapterWriterOutput(
            tour_title=written.title,
            tts_style=TTSStyle.model_validate(written.output.tts_style),
            chapters=[
                Chapter(title=item.title, narration=item.narration)
                for item in written.output.chapters
            ],
        )
        narrated = await pipeline.narrate_tour(
            chapters=chapters,
            tts_provider=self.tts,
            voice=input.voice,
            model=input.tts_model,
            audio_format=input.audio_format,
        )
        if len(narrated.chapters) != len(written.output.chapters):
            raise ValueError("Narration does not match chapter count")

        completed: list[TourChapter] = []
        for chapter, audio in zip(
            written.output.chapters,
            narrated.chapters,
            strict=True,
        ):
            if chapter.title != audio.title:
                raise ValueError(f"Narration title mismatch: {chapter.title}")
            path = self.audio.save(
                owner_id=owner_id,
                tour_id=tour_id,
                position=chapter.position,
                audio_format=audio.audio_format,
                media_type=audio.media_type,
                audio=audio.audio,
            )
            completed.append(
                chapter.model_copy(
                    update={
                        "audio_path": path,
                        "duration_seconds": audio.duration_seconds,
                    }
                )
            )
        return written.output.model_copy(update={"chapters": completed})


def _agent_plan(plan: TourPlanPayload) -> CheckpointResearchOutput:
    return CheckpointResearchOutput(
        narrative_arc=plan.narrative_arc,
        response_to_user=plan.response_to_user or "Approved tour plan.",
        ordered_checkpoints=[
            CheckpointProposal(
                title=item.title,
                brief_description=item.description,
                route_reasoning=item.route_reasoning,
                distance_tool_place_name=item.distance_tool_place_name,
            )
            for item in plan.checkpoints
        ],
    )
