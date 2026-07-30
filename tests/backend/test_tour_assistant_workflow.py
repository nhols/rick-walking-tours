import unittest
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

from pydantic_ai import ModelRequest, ModelResponse, TextPart, UserPromptPart
from pydantic_core import to_jsonable_python

from tour_gen.backend.assistant import (
    TourAssistantInput,
    TourAssistantOutput,
    TourAssistantReply,
    TourAssistantTextContent,
    TourAssistantTurn,
    TourAssistantUiContext,
    answer_tour_question,
)
from tour_worker.handler import handler


TOUR_ID = uuid4()
USER_ID = uuid4()
THREAD_ID = uuid4()
CHAPTER_ID = uuid4()
TURN_ID = uuid4()
MIGRATION = (
    Path(__file__).parents[2]
    / "supabase"
    / "migrations"
    / "20260730020000_tour_assistant_turns.sql"
)
TOUR_COMMANDS = (
    Path(__file__).parents[2]
    / "supabase"
    / "functions"
    / "tour-commands"
    / "index.ts"
)
WORKER_INVOKER = (
    Path(__file__).parents[2]
    / "supabase"
    / "functions"
    / "_shared"
    / "worker-invoker.ts"
)


def messages(prompt: str, response: str) -> list[dict[str, object]]:
    return to_jsonable_python(
        [
            ModelRequest(parts=[UserPromptPart(content=prompt)]),
            ModelResponse(parts=[TextPart(content=response)]),
        ]
    )


def assistant_input(text: str, playback_seconds: float = 42) -> TourAssistantInput:
    return TourAssistantInput(
        content=[TourAssistantTextContent(text=text)],
        context=TourAssistantUiContext(
            selected_chapter_id=CHAPTER_ID,
            chapter_playback_seconds=playback_seconds,
        ),
    )


def assistant_output(text: str) -> TourAssistantOutput:
    return TourAssistantOutput(content=[TourAssistantTextContent(text=text)])


class TourAssistantWorkflowTest(unittest.IsolatedAsyncioTestCase):
    @patch(
        "tour_gen.backend.assistant.tour_assistant_agent.run",
        new_callable=AsyncMock,
    )
    async def test_existing_thread_history_is_loaded_and_new_turn_is_saved(
        self,
        run: AsyncMock,
    ) -> None:
        existing_messages = messages("First question", "First answer")
        store = Mock()
        store.get_turns.return_value = [
            TourAssistantTurn(
                id=TURN_ID,
                tour_id=TOUR_ID,
                user_id=USER_ID,
                thread_id=THREAD_ID,
                turn=1,
                input=assistant_input("First question"),
                output=assistant_output("First answer"),
                new_messages=existing_messages,
            )
        ]
        result = Mock(output="Second answer")
        result.new_messages.return_value = [
            ModelRequest(parts=[UserPromptPart(content="Second question")]),
            ModelResponse(parts=[TextPart(content="Second answer")]),
        ]
        run.return_value = result
        context_loader = Mock()

        reply = await answer_tour_question(
            store,
            context_loader,
            tour_id=TOUR_ID,
            user_id=USER_ID,
            input=assistant_input("Second question"),
        )

        self.assertEqual(reply.thread_id, THREAD_ID)
        self.assertEqual(reply.turn, 2)
        store.ensure_tour_access.assert_called_once_with(TOUR_ID, USER_ID)
        run_call = run.await_args
        assert run_call is not None
        self.assertEqual(run_call.args, ("Second question",))
        self.assertEqual(len(run_call.kwargs["message_history"]), 2)
        self.assertEqual(run_call.kwargs["conversation_id"], str(THREAD_ID))
        store.save_turn.assert_called_once()
        saved = store.save_turn.call_args.kwargs
        self.assertEqual(saved["thread_id"], THREAD_ID)
        self.assertEqual(saved["turn"], 2)
        self.assertEqual(saved["input"].text(), "Second question")
        self.assertEqual(saved["output"].content[0].text, "Second answer")
        self.assertEqual(len(saved["new_messages"]), 2)


class TourAssistantHandlerTest(unittest.TestCase):
    @patch("tour_worker.handler.answer_tour_question", new_callable=AsyncMock)
    @patch("tour_worker.handler.create_supabase_client")
    def test_assistant_event_returns_reply(
        self,
        create_client: Mock,
        answer: AsyncMock,
    ) -> None:
        create_client.return_value = Mock()
        answer.return_value = TourAssistantReply(
            thread_id=THREAD_ID,
            turn=1,
            input=assistant_input("What is this?", 12),
            output=assistant_output("It is the first stop."),
        )

        response = handler(
            {
                "action": "ask_tour",
                "tour_id": str(TOUR_ID),
                "user_id": str(USER_ID),
                "input": {
                    "version": 1,
                    "content": [{"type": "text", "text": "What is this?"}],
                    "context": {
                        "selected_chapter_id": str(CHAPTER_ID),
                        "chapter_playback_seconds": 12,
                    },
                },
            },
            Mock(),
        )

        self.assertEqual(
            response,
            {
                "thread_id": str(THREAD_ID),
                "turn": 1,
                "input": {
                    "version": 1,
                    "content": [{"type": "text", "text": "What is this?"}],
                    "context": {
                        "selected_chapter_id": str(CHAPTER_ID),
                        "chapter_playback_seconds": 12.0,
                    },
                },
                "output": {
                    "version": 1,
                    "content": [
                        {"type": "text", "text": "It is the first stop."}
                    ],
                },
            },
        )
        answer.assert_awaited_once()


class TourAssistantMigrationTest(unittest.TestCase):
    def test_turns_are_private_and_unique_within_thread(self) -> None:
        sql = MIGRATION.read_text()

        self.assertIn("unique (tour_id, user_id, thread_id, turn)", sql)
        self.assertIn("input jsonb not null", sql)
        self.assertIn("output jsonb not null", sql)
        self.assertIn("using (user_id = auth.uid())", sql)
        self.assertIn("grant select on public.tour_assistant_turns", sql)
        self.assertNotIn("grant insert", sql)

    def test_edge_function_authorizes_and_invokes_assistant_synchronously(self) -> None:
        commands = TOUR_COMMANDS.read_text()
        invoker = WORKER_INVOKER.read_text()

        self.assertIn('if (action === "ask")', commands)
        self.assertIn('.from("tours")', commands)
        self.assertIn("user_id: userData.user.id", commands)
        self.assertIn('InvocationType: "RequestResponse"', invoker)


if __name__ == "__main__":
    unittest.main()
