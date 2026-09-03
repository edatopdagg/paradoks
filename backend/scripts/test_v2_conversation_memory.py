import unittest
from unittest.mock import patch

from app.services.chat_orchestrator import (
    generate_chat_response,
)
from app.services.conversation_memory import (
    clear_conversation_memory,
    get_recent_turns,
)


def _source() -> dict:
    return {
        "org": "3GPP",
        "code": "TS 23.501",
        "version": "20.2.0",
        "clause": "4.2.7",
        "clause_title": "Reference points",
        "status": "indexed",
        "source_url": "https://example.test/23501",
        "distance": 0.12,
    }


class ConversationMemoryTests(
    unittest.TestCase
):
    def setUp(self) -> None:
        clear_conversation_memory()

    def test_stores_turn_under_conversation_id(
        self,
    ) -> None:
        with patch(
            "app.services.chat_orchestrator.generate_reply",
            return_value={
                "reply": (
                    "N1, UE ile AMF arasındaki "
                    "referans noktasıdır."
                ),
                "sources": [_source()],
                "blocked_sources": [],
            },
        ):
            generate_chat_response(
                message="N1 referans noktası nedir?",
                conversation_id="conversation-memory",
            )

        turns = get_recent_turns(
            "conversation-memory"
        )

        self.assertEqual(
            len(turns),
            1,
        )

        self.assertIn(
            "N1",
            turns[0].user_message,
        )

        self.assertIn(
            "UE",
            turns[0].assistant_message,
        )

    def test_follow_up_receives_previous_context(
        self,
    ) -> None:
        conversation_id = (
            "conversation-follow-up"
        )

        first_question = (
            "N1 referans noktası nedir?"
        )

        first_answer = (
            "N1, UE ile AMF arasındaki "
            "referans noktasıdır."
        )

        follow_up = (
            "Peki bunun AMF açısından görevi nedir?"
        )

        with patch(
            "app.services.chat_orchestrator.generate_reply",
            return_value={
                "reply": first_answer,
                "sources": [_source()],
                "blocked_sources": [],
            },
        ) as first_call:
            first_result = (
                generate_chat_response(
                    message=first_question,
                    conversation_id=conversation_id,
                )
            )

        self.assertEqual(
            first_call.call_args.args[0],
            first_question.rstrip("?"),
        )

        self.assertEqual(
            first_result["conversation_id"],
            conversation_id,
        )

        with patch(
            "app.services.chat_orchestrator.generate_reply",
            return_value={
                "reply": (
                    "AMF, N1 üzerinden UE ile "
                    "NAS sinyalleşmesini yürütür."
                ),
                "sources": [_source()],
                "blocked_sources": [],
            },
        ) as follow_up_call:
            second_result = (
                generate_chat_response(
                    message=follow_up,
                    conversation_id=conversation_id,
                )
            )

        contextual_query = (
            follow_up_call
            .call_args
            .args[0]
        )

        self.assertIn(
            follow_up.rstrip("?"),
            contextual_query,
        )

        self.assertIn(
            first_question.rstrip("?"),
            contextual_query,
        )

        self.assertIn(
            first_answer,
            contextual_query,
        )

        self.assertEqual(
            second_result["conversation_id"],
            conversation_id,
        )

        self.assertEqual(
            second_result["detected_language"],
            "tr",
        )

    def test_unrelated_question_is_not_polluted_by_history(
        self,
    ) -> None:
        conversation_id = (
            "conversation-independent"
        )

        with patch(
            "app.services.chat_orchestrator.generate_reply",
            return_value={
                "reply": "N1 cevabı",
                "sources": [_source()],
                "blocked_sources": [],
            },
        ):
            generate_chat_response(
                message="N1 referans noktası nedir?",
                conversation_id=conversation_id,
            )

        unrelated = (
            "HTTP/3 hangi taşıma protokolünü kullanır?"
        )

        with patch(
            "app.services.chat_orchestrator.generate_reply",
            return_value={
                "reply": "HTTP/3 QUIC kullanır.",
                "sources": [_source()],
                "blocked_sources": [],
            },
        ) as mocked:
            generate_chat_response(
                message=unrelated,
                conversation_id=conversation_id,
            )

        self.assertEqual(
            mocked.call_args.args[0],
            unrelated.rstrip("?"),
        )


if __name__ == "__main__":
    unittest.main(
        verbosity=2
    )
