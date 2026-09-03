import unittest
from unittest.mock import call, patch

from app.services.chat_orchestrator import (
    generate_chat_response,
)
from app.services.conversation_memory import (
    clear_conversation_memory,
)


def _source(
    clause: str,
) -> dict:
    return {
        "org": "3GPP",
        "code": "TS 23.501",
        "version": "18.5.0",
        "clause": clause,
        "clause_title": "Reference points",
        "status": "indexed",
        "source_url": "https://example.test/23501",
        "distance": 0.12,
    }


class ChatOrchestratorTests(unittest.TestCase):
    def setUp(self) -> None:
        clear_conversation_memory()

    def test_echoes_existing_conversation_id(self) -> None:
        with patch(
            "app.services.chat_orchestrator.generate_reply",
            return_value={
                "reply": "N1 is a reference point.",
                "sources": [_source("4.2.7")],
                "blocked_sources": [],
            },
        ):
            result = generate_chat_response(
                message="What is the N1 reference point?",
                conversation_id="conversation-123",
            )

        self.assertEqual(
            result["conversation_id"],
            "conversation-123",
        )
        self.assertEqual(
            result["detected_language"],
            "en",
        )

    def test_generates_new_conversation_id(self) -> None:
        with patch(
            "app.services.chat_orchestrator.generate_reply",
            return_value={
                "reply": "N1 bir referans noktasıdır.",
                "sources": [_source("4.2.7")],
                "blocked_sources": [],
            },
        ):
            result = generate_chat_response(
                message="N1 referans noktası nedir?",
                conversation_id=None,
            )

        self.assertTrue(
            result["conversation_id"],
        )

    def test_runs_retrieval_for_each_subquestion(self) -> None:
        first_question = (
            "N1 üzerinden hangi sinyalleşme taşınır"
        )
        second_question = (
            "bu sinyalleşme neden NAS olarak adlandırılır"
        )

        with patch(
            "app.services.chat_orchestrator.generate_reply",
            side_effect=[
                {
                    "reply": (
                        "N1 üzerinden NAS sinyalleşmesi taşınır."
                    ),
                    "sources": [_source("4.2.7")],
                    "blocked_sources": [],
                },
                {
                    "reply": (
                        "NAS, erişim katmanı dışındaki "
                        "sinyalleşmeyi ifade eder."
                    ),
                    "sources": [_source("3.1")],
                    "blocked_sources": [],
                },
            ],
        ) as mocked_generate_reply:
            result = generate_chat_response(
                message=(
                    f"{first_question} ve "
                    f"{second_question}?"
                ),
                conversation_id="conversation-123",
            )

        self.assertEqual(
            mocked_generate_reply.call_args_list,
            [
                call(first_question),
                call(second_question),
            ],
        )

        self.assertEqual(
            len(result["questions"]),
            2,
        )

        self.assertTrue(
            all(
                question["answered"]
                for question in result["questions"]
            )
        )

        self.assertIn(
            "N1 üzerinden NAS",
            result["standard_answer"],
        )

        self.assertIn(
            "NAS, erişim katmanı",
            result["standard_answer"],
        )

        self.assertEqual(
            len(result["sources"]),
            2,
        )

        self.assertEqual(
            result["reply"],
            result["standard_answer"],
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)