import importlib
import sys
import types
import unittest
from unittest.mock import patch


class _DummyArray:
    def __init__(self, value):
        self.value = value

    def tolist(self):
        return self.value


class _DummySentenceTransformer:
    def __init__(self, *args, **kwargs):
        pass

    def encode(self, value, **kwargs):
        if isinstance(value, list):
            return _DummyArray([[0.0] for _ in value])
        return _DummyArray([0.0])


class _DummyCrossEncoder:
    def __init__(self, *args, **kwargs):
        pass

    def predict(self, pairs, **kwargs):
        return [0.0 for _ in pairs]


class _DummyCollection:
    def count(self):
        return 0

    def query(self, **kwargs):
        return {
            "ids": [],
            "documents": [],
            "metadatas": [],
            "distances": [],
        }

    def get(self, **kwargs):
        return {
            "ids": [],
            "documents": [],
            "metadatas": [],
        }


class _DummyClient:
    def __init__(self, *args, **kwargs):
        self.collection = _DummyCollection()

    def get_collection(self, **kwargs):
        return self.collection


def _load_chat_service():
    fake_chromadb = types.ModuleType("chromadb")
    fake_chromadb.PersistentClient = _DummyClient

    fake_transformers = types.ModuleType("sentence_transformers")
    fake_transformers.SentenceTransformer = _DummySentenceTransformer
    fake_transformers.CrossEncoder = _DummyCrossEncoder

    fake_dotenv = types.ModuleType("dotenv")
    fake_dotenv.load_dotenv = lambda *args, **kwargs: False

    fake_requests = types.ModuleType("requests")
    fake_requests.Timeout = RuntimeError
    fake_requests.ConnectionError = RuntimeError
    fake_requests.HTTPError = RuntimeError
    fake_requests.RequestException = RuntimeError
    fake_requests.post = lambda *args, **kwargs: None

    sys.modules.setdefault("chromadb", fake_chromadb)
    sys.modules.setdefault("sentence_transformers", fake_transformers)
    sys.modules.setdefault("dotenv", fake_dotenv)
    sys.modules.setdefault("requests", fake_requests)

    return importlib.import_module("app.services.chat_service")


def _chunk(
    text: str,
    *,
    code: str,
    clause: str = "1",
    clause_title: str = "Scope",
    source_url: str = "https://example.test/spec.zip",
) -> dict:
    return {
        "chunk_id": f"{code}-{clause}-{abs(hash(text))}",
        "text": text,
        "metadata": {
            "org": "3GPP",
            "code": code,
            "version": "V1.0.0",
            "clause": clause,
            "clause_title": clause_title,
            "source_url": source_url,
            "status": "indexed",
        },
        "distance": 0.2,
    }


class _FakeRetriever:
    def __init__(self, results):
        self.results = results
        self.calls = []

    def search(self, *, query, top_k, where=None):
        self.calls.append(
            {
                "query": query,
                "top_k": top_k,
                "where": where,
            }
        )
        return list(self.results)


class _FakeReranker:
    def rerank(self, query, candidates, top_k):
        ranked = []
        for index, candidate in enumerate(candidates):
            item = dict(candidate)
            item["rerank_score"] = 1.0 - (index * 0.1)
            ranked.append(item)
        return ranked[:top_k]


class ChatPipelineRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.chat_service = _load_chat_service()

    def _low_confidence_composer(self, question, chunks):
        return (
            {
                "answer_type": "GENEL TEKNİK BİLGİ",
                "primary_answer": "",
                "confidence": "low",
            },
            {
                "success": False,
                "reply": "",
            },
        )

    def test_explicit_document_is_sent_to_chroma_as_metadata_filter(self):
        service = self.chat_service
        correct = _chunk(
            "The present document specifies procedures for the 5G System.",
            code="TS 23.502",
        )
        fake_retriever = _FakeRetriever([correct])
        ollama_calls = []

        def fake_ollama(system_prompt, user_prompt):
            ollama_calls.append(user_prompt)
            return "Standart, 5G sistem prosedürlerini tanımlar."

        with (
            patch.object(service, "retriever", fake_retriever),
            patch.object(service, "reranker", _FakeReranker()),
            patch.object(service, "_compose_and_render", self._low_confidence_composer),
            patch.object(service, "generate_with_ollama", fake_ollama),
        ):
            response = service.generate_reply(
                "3GPP TS 23.502'de tanımlanan prosedürlere örnek ver."
            )

        self.assertEqual(
            fake_retriever.calls[0]["where"],
            {
                "$and": [
                    {"org": "3GPP"},
                    {"code": "TS 23.502"},
                ]
            },
        )
        self.assertEqual(len(ollama_calls), 1)
        self.assertEqual(response["sources"][0]["code"], "TS 23.502")

    def test_n1_content_question_cannot_return_one_word_fast_path(self):
        service = self.chat_service
        normal = _chunk(
            "N1 is the reference point between the UE and the AMF.",
            code="TS 23.501",
            clause="4.2.7",
            clause_title="Reference points",
        )
        fallback = _chunk(
            "NAS signalling between UE and AMF is transferred via N1.",
            code="TS 23.501",
            clause="4.2.7",
            clause_title="Reference points",
        )
        fake_retriever = _FakeRetriever([normal])
        ollama_calls = []

        def high_identity_composer(question, chunks):
            return (
                {
                    "answer_type": "ARAYÜZ / REFERANS NOKTASI",
                    "primary_answer": "N1",
                    "confidence": "high",
                },
                {
                    "success": True,
                    "reply": "İlgili referans noktası N1'dir.",
                },
            )

        def fake_ollama(system_prompt, user_prompt):
            ollama_calls.append(user_prompt)
            return "N1 üzerinden UE ile AMF arasında NAS sinyalleşmesi taşınır."

        with (
            patch.object(service, "retriever", fake_retriever),
            patch.object(service, "reranker", _FakeReranker()),
            patch.object(service, "_compose_and_render", high_identity_composer),
            patch.object(service, "_targeted_fallback_retrieval", lambda question: [fallback]),
            patch.object(service, "generate_with_ollama", fake_ollama),
        ):
            response = service.generate_reply(
                "N1 referans noktası üzerinden UE ile AMF arasında "
                "hangi tür sinyalleşme taşınır?"
            )

        self.assertEqual(len(ollama_calls), 1)
        self.assertIn("NAS sinyalleşmesi", response["reply"])
        self.assertNotEqual(response["reply"], "İlgili referans noktası N1'dir.")

    def test_failed_precision_route_abstains_without_calling_ollama(self):
        service = self.chat_service
        normal = _chunk(
            "N3 is a reference point in the 5G System.",
            code="TS 24.554",
            clause="8.2.6.4.1",
            clause_title="General",
        )
        fake_retriever = _FakeRetriever([normal])
        ollama_calls = []

        with (
            patch.object(service, "retriever", fake_retriever),
            patch.object(service, "reranker", _FakeReranker()),
            patch.object(service, "_compose_and_render", self._low_confidence_composer),
            patch.object(service, "_targeted_fallback_retrieval", lambda question: []),
            patch.object(
                service,
                "generate_with_ollama",
                lambda *args, **kwargs: ollama_calls.append(True),
            ),
        ):
            response = service.generate_reply(
                "N3 referans noktasının 5G mimarisindeki görevi nedir?"
            )

        self.assertEqual(ollama_calls, [])
        self.assertEqual(
            response["reply"],
            "Bu soruyu yanıtlamak için yeterli standart bilgisi bulunamadı.",
        )

    def test_low_confidence_reference_fallback_is_used_by_ollama(self):
        service = self.chat_service
        normal = _chunk(
            "Location services may use N1 for a service-specific message.",
            code="TS 23.273",
            clause="4.1",
            clause_title="General Concepts",
        )
        fallback = _chunk(
            "NAS signalling between the UE and the AMF is transferred via N1.",
            code="TS 23.501",
            clause="4.2.7",
            clause_title="Reference points",
        )
        fake_retriever = _FakeRetriever([normal])
        prompts = []

        def fake_ollama(system_prompt, user_prompt):
            prompts.append(user_prompt)
            return "N1 üzerinden UE ile AMF arasında NAS sinyalleşmesi taşınır."

        with (
            patch.object(service, "retriever", fake_retriever),
            patch.object(service, "reranker", _FakeReranker()),
            patch.object(service, "_compose_and_render", self._low_confidence_composer),
            patch.object(service, "_targeted_fallback_retrieval", lambda question: [fallback]),
            patch.object(service, "generate_with_ollama", fake_ollama),
        ):
            response = service.generate_reply(
                "N1 referans noktası üzerinden UE ile AMF arasında "
                "hangi tür sinyalleşme taşınır?"
            )

        self.assertEqual(len(prompts), 1)
        self.assertIn("NAS signalling", prompts[0])
        self.assertNotIn("Location services", prompts[0])
        self.assertEqual(response["sources"][0]["code"], "TS 23.501")

    def test_strong_rerank_margin_uses_one_chunk_for_single_question(self):
        service = self.chat_service
        first = _chunk(
            "Direct evidence.",
            code="TS 23.501",
        )
        first["rerank_score"] = 8.2
        second = _chunk(
            "Secondary evidence.",
            code="TS 23.273",
        )
        second["rerank_score"] = 5.4

        selected = service._select_prompt_results(
            "N1 üzerinden hangi sinyalleşme taşınır?",
            [first, second],
        )

        self.assertEqual(len(selected), 1)
        self.assertEqual(selected[0]["metadata"]["code"], "TS 23.501")

    def test_reference_point_fts_uses_entity_relation_and_endpoints(self):
        service = self.chat_service
        queries = service._reference_point_fts_queries(
            "N1 referans noktası üzerinden UE ile AMF arasında "
            "hangi tür sinyalleşme taşınır?"
        )

        self.assertEqual(
            queries[0],
            '"N1" AND "NAS" AND "UE" AND "AMF"',
        )

    def test_reference_fallback_reranks_with_technical_variants(self):
        service = self.chat_service
        candidate = _chunk(
            "NAS signalling between UE and AMF is transferred via N1.",
            code="TS 23.501",
            clause="4.2.7",
            clause_title="Reference points",
        )

        class FakeLexicalSearch:
            def __init__(self):
                self.calls = []

            def search_query(self, *, query, limit):
                self.calls.append(query)
                return [candidate]

        class FakeNormalizer:
            def normalize(self, question, max_variants):
                return [
                    question,
                    "N1 NAS signalling between UE and AMF",
                    "N1 reference point between UE and AMF",
                ]

        class FakeFallbackRetriever:
            query_normalizer = FakeNormalizer()

        class CapturingReranker:
            def __init__(self):
                self.candidates = []

            def rerank(self, query, candidates, top_k):
                self.candidates = candidates
                ranked = dict(candidates[0])
                ranked["rerank_score"] = 4.2
                return [ranked]

        fake_lexical = FakeLexicalSearch()
        capturing_reranker = CapturingReranker()

        with (
            patch.object(service, "lexical_search", fake_lexical),
            patch.object(service, "retriever", FakeFallbackRetriever()),
            patch.object(service, "reranker", capturing_reranker),
        ):
            results = service._targeted_fallback_retrieval(
                "N1 referans noktası üzerinden UE ile AMF arasında "
                "hangi tür sinyalleşme taşınır?"
            )

        self.assertEqual(
            fake_lexical.calls,
            ['"N1" AND "NAS" AND "UE" AND "AMF"'],
        )
        self.assertIn(
            "N1 NAS signalling between UE and AMF",
            capturing_reranker.candidates[0]["matched_queries"],
        )
        self.assertEqual(results[0]["rerank_score"], 4.2)

    def test_negative_precision_fallback_scores_are_rejected(self):
        service = self.chat_service
        normal = _chunk(
            "S1 signalling bearer.",
            code="TS 36.412",
            clause="4",
            clause_title="S1 signalling bearer",
        )
        fallback = _chunk(
            "A service-specific N1 signalling procedure.",
            code="TS 24.501",
            clause="5.3.1.3",
            clause_title="5GMM-IDLE mode",
        )
        fallback["rerank_score"] = -3.8
        fake_retriever = _FakeRetriever([normal])
        ollama_calls = []

        with (
            patch.object(service, "retriever", fake_retriever),
            patch.object(service, "reranker", _FakeReranker()),
            patch.object(service, "_compose_and_render", self._low_confidence_composer),
            patch.object(service, "_targeted_fallback_retrieval", lambda question: [fallback]),
            patch.object(
                service,
                "generate_with_ollama",
                lambda *args, **kwargs: ollama_calls.append(True),
            ),
        ):
            response = service.generate_reply(
                "N1 referans noktası üzerinden UE ile AMF arasında "
                "hangi tür sinyalleşme taşınır?"
            )

        self.assertEqual(ollama_calls, [])
        self.assertEqual(
            response["reply"],
            "Bu soruyu yanıtlamak için yeterli standart bilgisi bulunamadı.",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
