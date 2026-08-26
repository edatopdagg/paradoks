import unittest

from app.services.answer_guard import validate_answer
from app.services.prompt_builder import infer_answer_type
from app.services.query_normalizer import QueryNormalizer
from app.services.question_analysis import (
    allows_deterministic_fast_path,
    build_result_deduplication_key,
    extract_document_constraint,
    has_usable_evidence,
    is_low_value_clause,
)


def _chunk(
    text: str,
    *,
    org: str = "3GPP",
    code: str = "TS 23.502",
    clause: str = "1",
    clause_title: str = "Scope",
    source_url: str = "https://example.test/spec.zip",
) -> dict:
    return {
        "text": text,
        "metadata": {
            "org": org,
            "code": code,
            "clause": clause,
            "clause_title": clause_title,
            "source_url": source_url,
            "status": "indexed",
        },
    }


class QuestionIntentRegressionTests(unittest.TestCase):
    def test_reference_point_content_question_is_not_identity_lookup(self) -> None:
        question = (
            "N1 referans noktası üzerinden UE ile AMF arasında "
            "hangi tür sinyalleşme taşınır?"
        )
        self.assertEqual(
            infer_answer_type(question),
            "GENEL TEKNİK BİLGİ",
        )

    def test_reference_point_purpose_question_is_purpose(self) -> None:
        self.assertEqual(
            infer_answer_type(
                "N3 referans noktasının 5G mimarisindeki görevi nedir?"
            ),
            "AMAÇ / İŞLEV",
        )

    def test_procedure_purpose_question_is_not_procedure_identity(self) -> None:
        question = (
            "Warning Message Cancel Procedure hangi amaçla kullanılır "
            "ve iptal edilecek mesaj nasıl belirlenir?"
        )
        self.assertEqual(
            infer_answer_type(question),
            "AMAÇ / İŞLEV",
        )

    def test_exact_reference_point_lookup_stays_deterministic(self) -> None:
        question = "UE ile AMF arasındaki referans noktası hangisidir?"
        answer_type = infer_answer_type(question)
        self.assertEqual(answer_type, "ARAYÜZ / REFERANS NOKTASI")
        self.assertTrue(
            allows_deterministic_fast_path(question, answer_type)
        )

    def test_explanatory_and_multi_part_questions_skip_fast_path(self) -> None:
        cases = (
            (
                "N1 referans noktası üzerinden hangi tür sinyalleşme taşınır?",
                "ARAYÜZ / REFERANS NOKTASI",
            ),
            (
                "Warning Message Cancel Procedure hangi amaçla kullanılır "
                "ve mesaj nasıl belirlenir?",
                "PROSEDÜR",
            ),
            (
                "HTTP'te idempotent ne demektir ve neden önemlidir?",
                "DEĞER / LİMİT",
            ),
        )

        for question, answer_type in cases:
            with self.subTest(question=question):
                self.assertFalse(
                    allows_deterministic_fast_path(question, answer_type)
                )


class DocumentConstraintRegressionTests(unittest.TestCase):
    def test_extracts_3gpp_ts_constraint(self) -> None:
        self.assertEqual(
            extract_document_constraint(
                "3GPP TS 23.502'de tanımlanan prosedürlere örnek ver."
            ),
            {"org": "3GPP", "code": "TS 23.502"},
        )

    def test_extracts_rfc_constraint(self) -> None:
        self.assertEqual(
            extract_document_constraint("RFC 9110'a göre idempotency nedir?"),
            {"org": "IETF", "code": "9110"},
        )

    def test_extracts_etsi_constraint(self) -> None:
        self.assertEqual(
            extract_document_constraint("ETSI TS 123 041 neyi tanımlar?"),
            {"org": "ETSI", "code": "TS 123 041"},
        )

    def test_evidence_must_match_explicit_document(self) -> None:
        question = "3GPP TS 23.502'de tanımlanan prosedürlere örnek ver."

        correct = _chunk(
            "The present document specifies procedures for the 5G System.",
            code="TS 23.502",
        )
        wrong = _chunk(
            "This document specifies a different service.",
            code="TS 29.534",
        )

        self.assertTrue(has_usable_evidence(question, [correct]))
        self.assertFalse(has_usable_evidence(question, [wrong]))


class SourceQualityRegressionTests(unittest.TestCase):
    def test_reference_and_change_history_are_low_value(self) -> None:
        self.assertTrue(is_low_value_clause("2", "References"))
        self.assertTrue(is_low_value_clause("A.3", "Change history"))
        self.assertFalse(is_low_value_clause("4.2.7", "Reference points"))

    def test_ts_tr_duplicate_uses_url_clause_and_text(self) -> None:
        ts_result = _chunk(
            "Same normalized evidence text.",
            code="TS 23.501",
            clause="4.2.7",
        )
        tr_result = _chunk(
            "  Same   normalized evidence text.  ",
            code="TR 23.501",
            clause="4.2.7",
        )

        self.assertEqual(
            build_result_deduplication_key(ts_result),
            build_result_deduplication_key(tr_result),
        )

    def test_only_reference_evidence_is_rejected(self) -> None:
        chunk = _chunk(
            "[1] 3GPP TS 23.502 Procedures for the 5G System.",
            clause="2",
            clause_title="References",
        )
        self.assertFalse(
            has_usable_evidence(
                "5GS NAS protokolü hangi işlemleri yönetir?",
                [chunk],
            )
        )


class AnswerGuardRegressionTests(unittest.TestCase):
    def test_rejects_unsupported_http_status_codes(self) -> None:
        chunks = [
            _chunk(
                "A request method is idempotent if multiple identical "
                "requests have the same intended effect as one request.",
                org="IETF",
                code="9110",
                clause="9.2.2",
                clause_title="Idempotent Methods",
            )
        ]
        result = validate_answer(
            question=(
                "PUT veya DELETE isteği birden fazla kez gönderildiğinde "
                "beklenen davranış nedir?"
            ),
            reply=(
                "Her tekrar aynı HTTP durum kodunu, örneğin 200 veya 409, "
                "döndürmelidir."
            ),
            chunks=chunks,
        )
        self.assertFalse(result["valid"])

    def test_rejects_unsupported_acronym_expansion(self) -> None:
        chunks = [
            _chunk(
                "Architectural enhancements to the 5G System using NR "
                "to support multicast and broadcast communication services.",
                code="TS 23.247",
            )
        ]
        result = validate_answer(
            question="5G multicast-broadcast servisinin temel amacı nedir?",
            reply=(
                "Temel amaç, NR (Narrowband IoT) kullanarak çoklu yayın "
                "hizmetlerini desteklemektir."
            ),
            chunks=chunks,
        )
        self.assertFalse(result["valid"])


class QueryNormalizerRegressionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.normalizer = QueryNormalizer()

    def test_reference_point_code_gets_entity_aware_variants(self) -> None:
        variants = self.normalizer.normalize(
            "N3 referans noktasının görevi nedir?"
        )
        self.assertIn("N3 reference point", variants)

    def test_reference_point_signalling_gets_relation_variant(self) -> None:
        variants = self.normalizer.normalize(
            "N1 referans noktası üzerinden UE ile AMF arasında "
            "hangi tür sinyalleşme taşınır?"
        )
        self.assertIn(
            "N1 NAS signalling between UE and AMF",
            variants,
        )

    def test_quic_udp_gets_normative_phrase(self) -> None:
        variants = self.normalizer.normalize(
            "QUIC paketlerinin UDP datagramları içinde taşınması ne anlama gelir?"
        )
        self.assertIn(
            "QUIC packet is carried in a UDP datagram",
            variants,
        )

    def test_explicit_23502_gets_document_scope_variant(self) -> None:
        variants = self.normalizer.normalize(
            "3GPP TS 23.502'de tanımlanan prosedürlere örnek ver."
        )
        self.assertIn(
            "Procedures for the 5G System Stage 2",
            variants,
        )

    def test_http_idempotency_gets_normative_term(self) -> None:
        variants = self.normalizer.normalize(
            "HTTP'de bir metodun idempotent olması ne demektir?"
        )
        self.assertIn("Idempotent Methods", variants)


if __name__ == "__main__":
    unittest.main(verbosity=2)
