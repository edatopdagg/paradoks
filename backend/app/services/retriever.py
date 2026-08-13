import re
import time
from typing import Any

import chromadb

from app.core.config import (
    CHROMA_COLLECTION_NAME,
    CHROMA_DB_PATH,
    MAX_RETRIEVAL_DISTANCE,
)
from app.services.embedding_service import EmbeddingService


class Retriever:
    def __init__(self) -> None:
        self.embedding_service = EmbeddingService()

        self.client = chromadb.PersistentClient(
            path=str(CHROMA_DB_PATH)
        )

        self.collection = self.client.get_collection(
            name=CHROMA_COLLECTION_NAME
        )

    def _format_results(
        self,
        result: dict[str, Any],
    ) -> list[dict[str, Any]]:
        matches: list[dict[str, Any]] = []

        ids = result["ids"][0]
        documents = result["documents"][0]
        metadatas = result["metadatas"][0]
        distances = result["distances"][0]

        for chunk_id, document, metadata, distance in zip(
            ids,
            documents,
            metadatas,
            distances,
        ):
            if distance > MAX_RETRIEVAL_DISTANCE:
                continue

            matches.append(
                {
                    "chunk_id": chunk_id,
                    "text": document,
                    "metadata": metadata or {},
                    "distance": distance,
                }
            )

        return matches

    def _extract_keyword_phrases(
        self,
        query: str,
    ) -> list[str]:
        phrases: list[str] = []

        # Örnek:
        # Registration Request
        # Cell Broadcast
        title_case_phrases = re.findall(
            r"\b(?:[A-Z][a-z]+)(?:\s+[A-Z][a-z]+)+\b",
            query,
        )

        phrases.extend(title_case_phrases)

        # Örnek:
        # INVITE
        # SIP
        # PWS
        # RRC
        uppercase_terms = re.findall(
            r"\b[A-Z][A-Z0-9_-]{2,}\b",
            query,
        )

        phrases.extend(uppercase_terms)

        # Örnek:
        # RRCSetupRequest
        camel_case_terms = re.findall(
            r"\b[A-Z][A-Za-z0-9]*(?:Request|Response|Command|Reject|Accept)\b",
            query,
        )

        phrases.extend(camel_case_terms)

        # Aynı terimi iki kez alma.
        unique_phrases: list[str] = []

        for phrase in phrases:
            phrase = phrase.strip()

            if phrase and phrase not in unique_phrases:
                unique_phrases.append(phrase)

        return unique_phrases

    def _case_variants(
        self,
        phrase: str,
    ) -> list[str]:
        variants = [
            phrase,
            phrase.lower(),
            phrase.upper(),
            phrase.title(),
            phrase[:1].upper() + phrase[1:].lower(),
        ]

        unique_variants: list[str] = []

        for variant in variants:
            if variant and variant not in unique_variants:
                unique_variants.append(variant)

        return unique_variants

    def search(
        self,
        query: str,
        top_k: int = 3,
    ) -> list[dict[str, Any]]:
        clean_query = query.strip()

        if not clean_query:
            raise ValueError("Arama sorusu boş olamaz.")

        embedding_start = time.perf_counter()

        query_embedding = self.embedding_service.embed_query(
            clean_query
        )

        embedding_time = time.perf_counter() - embedding_start

        chroma_start = time.perf_counter()

        result = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            include=[
                "documents",
                "metadatas",
                "distances",
            ],
        )

        chroma_time = time.perf_counter() - chroma_start

        print(f"[PERF] Embedding: {embedding_time:.2f} sn")
        print(f"[PERF] Chroma Search: {chroma_time:.2f} sn")

        ids = result["ids"][0]
        documents = result["documents"][0]
        metadatas = result["metadatas"][0]
        distances = result["distances"][0]

        matches: list[dict[str, Any]] = []

        print()
        print("=" * 70)
        print(f"[RETRIEVAL] Soru: {clean_query}")
        print(f"[RETRIEVAL] İstenen top_k: {top_k}")
        print(
            f"[RETRIEVAL] Chroma'nın döndürdüğü sonuç: "
            f"{len(ids)}"
        )
        print("-" * 70)

        for index, (
            chunk_id,
            document,
            metadata,
            distance,
        ) in enumerate(
            zip(
                ids,
                documents,
                metadatas,
                distances,
            ),
            start=1,
        ):
            metadata = metadata or {}

            org = metadata.get("org", "Bilinmiyor")
            code = metadata.get("code", "Bilinmiyor")
            version = metadata.get("version", "Bilinmiyor")
            clause = metadata.get("clause", "Bilinmiyor")
            status = metadata.get("status", "Bilinmiyor")

            if distance > MAX_RETRIEVAL_DISTANCE:
                decision = "DROP"
            else:
                decision = "KEEP"

            print(
                f"{index}. [{decision}] "
                f"{org} {code} | "
                f"Version: {version} | "
                f"Clause: {clause} | "
                f"Status: {status} | "
                f"Distance: {distance:.4f}"
            )

            if distance > MAX_RETRIEVAL_DISTANCE:
                continue

            matches.append(
                {
                    "chunk_id": chunk_id,
                    "text": document,
                    "metadata": metadata,
                    "distance": distance,
                }
            )

        print("-" * 70)
        print(
            f"[RETRIEVAL] Distance filtresinden sonra kalan: "
            f"{len(matches)}"
        )
        print("=" * 70)
        print()

        return matches

    def hybrid_search(
        self,
        query: str,
        semantic_top_k: int = 20,
        keyword_top_k: int = 5,
    ) -> list[dict[str, Any]]:
        clean_query = query.strip()

        if not clean_query:
            raise ValueError("Arama sorusu boş olamaz.")

        hybrid_start = time.perf_counter()

        # -----------------------------------------------------
        # 1. EMBEDDING
        # -----------------------------------------------------
        embedding_start = time.perf_counter()

        query_embedding = self.embedding_service.embed_query(
            clean_query
        )

        embedding_time = time.perf_counter() - embedding_start

        # -----------------------------------------------------
        # 2. SEMANTIC SEARCH
        # -----------------------------------------------------
        semantic_start = time.perf_counter()

        semantic_result = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=semantic_top_k,
            include=[
                "documents",
                "metadatas",
                "distances",
            ],
        )

        semantic_time = time.perf_counter() - semantic_start

        semantic_matches = self._format_results(
            semantic_result
        )

        # -----------------------------------------------------
        # 3. TEKNİK TERİMLERİ ÇIKAR
        # -----------------------------------------------------
        keyword_phrases = self._extract_keyword_phrases(
            clean_query
        )

        print()
        print("=" * 70)
        print(f"[HYBRID] Soru: {clean_query}")
        print(
            f"[HYBRID] Semantic aday: "
            f"{len(semantic_matches)}"
        )
        print(
            f"[HYBRID] Bulunan teknik terimler: "
            f"{keyword_phrases}"
        )

        # -----------------------------------------------------
        # 4. KEYWORD-FILTERED VECTOR SEARCH
        # -----------------------------------------------------
        keyword_start = time.perf_counter()

        keyword_matches: list[dict[str, Any]] = []

        for phrase in keyword_phrases:
            variants = self._case_variants(phrase)

            print(
                f"[HYBRID] Keyword: {phrase} "
                f"-> variants: {variants}"
            )

            for variant in variants:
                try:
                    result = self.collection.query(
                        query_embeddings=[query_embedding],
                        n_results=keyword_top_k,
                        where_document={
                            "$contains": variant
                        },
                        include=[
                            "documents",
                            "metadatas",
                            "distances",
                        ],
                    )

                except Exception:
                    continue

                matches = self._format_results(result)

                keyword_matches.extend(matches)

        keyword_time = (
            time.perf_counter() - keyword_start
        )

        # -----------------------------------------------------
        # 5. SEMANTIC + KEYWORD MERGE / DEDUP
        # -----------------------------------------------------
        merged: dict[str, dict[str, Any]] = {}

        for result in semantic_matches:
            item = dict(result)
            item["retrieval_source"] = "semantic"

            merged[result["chunk_id"]] = item

        for result in keyword_matches:
            chunk_id = result["chunk_id"]

            if chunk_id in merged:
                merged[chunk_id]["retrieval_source"] = (
                    "semantic+keyword"
                )
            else:
                item = dict(result)
                item["retrieval_source"] = "keyword"
                merged[chunk_id] = item

        hybrid_matches = list(merged.values())

        # Vector distance'a göre başlangıç sıralaması.
        hybrid_matches.sort(
            key=lambda item: item["distance"]
        )

        hybrid_time = time.perf_counter() - hybrid_start

        # -----------------------------------------------------
        # DEBUG
        # -----------------------------------------------------
        print(
            f"[HYBRID] Keyword tarafının ürettiği "
            f"ham aday: {len(keyword_matches)}"
        )
        print(
            f"[HYBRID] Merge sonrası unique aday: "
            f"{len(hybrid_matches)}"
        )
        print("-" * 70)

        for index, result in enumerate(
            hybrid_matches,
            start=1,
        ):
            metadata = result["metadata"]

            print(
                f"{index}. "
                f"[{result['retrieval_source']}] "
                f"{metadata.get('org', 'Bilinmiyor')} "
                f"{metadata.get('code', 'Bilinmiyor')} | "
                f"Clause: "
                f"{metadata.get('clause', 'Bilinmiyor')} | "
                f"Distance: {result['distance']:.4f}"
            )

        print("-" * 70)
        print(
            f"[PERF] Hybrid Embedding: "
            f"{embedding_time:.2f} sn"
        )
        print(
            f"[PERF] Semantic Search: "
            f"{semantic_time:.2f} sn"
        )
        print(
            f"[PERF] Keyword Search: "
            f"{keyword_time:.2f} sn"
        )
        print(
            f"[PERF] Hybrid Total: "
            f"{hybrid_time:.2f} sn"
        )
        print("=" * 70)
        print()

        return hybrid_matches