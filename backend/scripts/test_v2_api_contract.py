import unittest

from app.schemas import (
    ChatRequest,
    ChatResponse,
    Source,
)


class ChatRequestContractTests(unittest.TestCase):
    def test_request_carries_conversation_id(self) -> None:
        request = ChatRequest(
            message="N1 referans noktası nedir?",
            conversation_id="conversation-123",
        )

        self.assertEqual(
            request.conversation_id,
            "conversation-123",
        )


class ChatResponseContractTests(unittest.TestCase):
    def test_response_contains_two_answer_types(self) -> None:
        response = ChatResponse(
            conversation_id="conversation-123",
            detected_language="tr",
            questions=[
                {
                    "text": "N1 üzerinden ne taşınır?",
                    "intent": "general",
                    "answered": True,
                }
            ],
            standard_answer=(
                "N1 üzerinden NAS sinyalleşmesi taşınır."
            ),
            assistant_answer=(
                "Bunu UE ile AMF arasındaki kontrol "
                "iletişimi olarak düşünebilirsin."
            ),
            reply="N1 üzerinden NAS sinyalleşmesi taşınır.",
            sources=[],
            blocked_sources=[],
        )

        self.assertEqual(
            response.detected_language,
            "tr",
        )
        self.assertTrue(
            response.standard_answer,
        )
        self.assertTrue(
            response.assistant_answer,
        )
        self.assertEqual(
            len(response.questions),
            1,
        )

    def test_old_response_shape_remains_valid(self) -> None:
        response = ChatResponse(
            reply="Eski cevap",
            sources=[],
            blocked_sources=[],
        )

        self.assertEqual(
            response.reply,
            "Eski cevap",
        )
        self.assertEqual(
            response.standard_answer,
            "",
        )
        self.assertEqual(
            response.assistant_answer,
            "",
        )


class SourceContractTests(unittest.TestCase):
    def test_source_can_carry_exact_location(self) -> None:
        source = Source(
            org="3GPP",
            code="TS 23.501",
            version="18.5.0",
            clause="4.2.7",
            clause_title="Reference points",
            status="indexed",
            source_url="https://example.test/source",
            distance=0.12,
            source_id="chunk-123",
            document_id="document-456",
            page_number=34,
            viewer_url=(
                "/sources/document-456"
                "?page=34&clause=4.2.7"
            ),
            highlight_text=(
                "NAS signalling between the UE and "
                "the AMF is transferred via N1."
            ),
        )

        self.assertEqual(
            source.page_number,
            34,
        )
        self.assertEqual(
            source.document_id,
            "document-456",
        )
        self.assertIn(
            "clause=4.2.7",
            source.viewer_url,
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)