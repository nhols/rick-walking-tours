from typing import Any, Literal, Protocol
from uuid import UUID, uuid4

from pydantic import BaseModel, Field
from pydantic_ai import ModelMessage, ModelMessagesTypeAdapter
from pydantic_core import to_jsonable_python

from tour_gen.agents.tour_assistant import (
    TourAssistantContextLoader,
    TourAssistantDeps,
    tour_assistant_agent,
)


class TourAssistantTextContent(BaseModel):
    type: Literal["text"] = "text"
    text: str = Field(min_length=1, max_length=4_000)


type TourAssistantContent = TourAssistantTextContent


class TourAssistantUiContext(BaseModel):
    selected_chapter_id: UUID
    chapter_playback_seconds: float = Field(ge=0)


class TourAssistantInput(BaseModel):
    version: Literal[1] = 1
    content: list[TourAssistantContent] = Field(min_length=1)
    context: TourAssistantUiContext

    def text(self) -> str:
        return "\n\n".join(block.text for block in self.content)


class TourAssistantOutput(BaseModel):
    version: Literal[1] = 1
    content: list[TourAssistantContent] = Field(min_length=1)


class TourAssistantTurn(BaseModel):
    id: UUID
    tour_id: UUID
    user_id: UUID
    thread_id: UUID
    turn: int
    input: TourAssistantInput
    output: TourAssistantOutput
    new_messages: list[dict[str, Any]]


class TourAssistantReply(BaseModel):
    thread_id: UUID
    turn: int
    input: TourAssistantInput
    output: TourAssistantOutput


class TourAssistantStore(Protocol):
    def ensure_tour_access(self, tour_id: UUID, user_id: UUID) -> None: ...

    def get_turns(
        self,
        tour_id: UUID,
        user_id: UUID,
    ) -> list[TourAssistantTurn]: ...

    def save_turn(
        self,
        *,
        tour_id: UUID,
        user_id: UUID,
        thread_id: UUID,
        turn: int,
        input: TourAssistantInput,
        output: TourAssistantOutput,
        new_messages: list[dict[str, Any]],
    ) -> None: ...


async def answer_tour_question(
    store: TourAssistantStore,
    context_loader: TourAssistantContextLoader,
    *,
    tour_id: UUID,
    user_id: UUID,
    input: TourAssistantInput,
) -> TourAssistantReply:
    store.ensure_tour_access(tour_id, user_id)
    turns = store.get_turns(tour_id, user_id)
    thread_id = turns[0].thread_id if turns else uuid4()
    turn_number = turns[-1].turn + 1 if turns else 1
    history = _message_history(turns)
    message = input.text()

    result = await tour_assistant_agent.run(
        message,
        deps=TourAssistantDeps(
            tour_id=tour_id,
            selected_chapter_id=input.context.selected_chapter_id,
            chapter_playback_seconds=input.context.chapter_playback_seconds,
            context_loader=context_loader,
        ),
        message_history=history or None,
        conversation_id=str(thread_id),
    )
    output = TourAssistantOutput(
        content=[TourAssistantTextContent(text=result.output)]
    )
    new_messages = to_jsonable_python(result.new_messages())
    store.save_turn(
        tour_id=tour_id,
        user_id=user_id,
        thread_id=thread_id,
        turn=turn_number,
        input=input,
        output=output,
        new_messages=new_messages,
    )
    return TourAssistantReply(
        thread_id=thread_id,
        turn=turn_number,
        input=input,
        output=output,
    )


def _message_history(turns: list[TourAssistantTurn]) -> list[ModelMessage]:
    return [
        message
        for turn in turns
        for message in ModelMessagesTypeAdapter.validate_python(turn.new_messages)
    ]
