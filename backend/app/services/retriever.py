import time
from typing import Any

import chromadb

from app.core.config import (
    CHROMA_COLLECTION_NAME,
    CHROMA_DB_PATH,
    MAX_RETRIEVAL_DISTANCE,
)
from app.services.embedding_service import EmbeddingService


DEFAULT_TOP_K = 3


class Retriever:
    def __init__(self) -> None:
        self.embedding_service = EmbeddingService()

        print(
            "[RETRIEVER] Chroma DB:",
            CHROMA_DB_PATH,
        )

        self.client = chromadb.PersistentClient(
            path=str(CHROMA_DB_PATH)
        )

        self.collection = self.client.get_collection(
            name=CHROMA_COLLECTION_NAME
        )

        print(
            "[RETRIEVER] Collection:",
            CHROMA_COLLECTION_NAME,
        )

        print(
            "[RETRIEVER] Toplam chunk:",
            self.collection.count(),
        )

    def _format_results(
        self,
        result: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """
        Chroma sonucunu uygulamanın kullandığı
        standart result yapısına dönüştürür.

        Distance threshold üzerinde kalan
        sonuçlar elenir.
        """

        matches: list[
            dict[str, Any]
        ] = []

        ids = result.get(
            "ids",
            [[]],
        )[0]

        documents = result.get(
            "documents",
            [[]],
        )[0]

        metadatas = result.get(
            "metadatas",
            [[]],
        )[0]

        distances = result.get(
            "distances",
            [[]],
        )[0]

        for (
            chunk_id,
            document,
            metadata,
            distance,
        ) in zip(
            ids,
            documents,
            metadatas,
            distances,
        ):
            if distance is None:
                continue

            if (
                distance
                > MAX_RETRIEVAL_DISTANCE
            ):
                continue

            clean_document = (
                document or ""
            ).strip()

            if not clean_document:
                continue

            matches.append(
                {
                    "chunk_id": chunk_id,
                    "text": clean_document,
                    "metadata": (
                        metadata or {}
                    ),
                    "distance": float(
                        distance
                    ),
                }
            )

        return matches

    def search(
        self,
        query: str,
        top_k: int = DEFAULT_TOP_K,
    ) -> list[dict[str, Any]]:
        """
        Semantic vector search.

        Yeni temiz DB doğrulanana kadar production
        retrieval yolu yalnızca budur.

        Eski Chroma where_document tabanlı keyword
        araması burada kullanılmaz çünkü büyük DB'de
        ciddi latency oluşturuyordu.
        """

        clean_query = (
            query or ""
        ).strip()

        if not clean_query:
            raise ValueError(
                "Arama sorusu boş olamaz."
            )

        if top_k <= 0:
            raise ValueError(
                "top_k sıfırdan büyük olmalıdır."
            )

        total_start = (
            time.perf_counter()
        )

        # -------------------------------------------------
        # 1. QUERY EMBEDDING
        # -------------------------------------------------
        embedding_start = (
            time.perf_counter()
        )

        query_embedding = (
            self.embedding_service.embed_query(
                clean_query
            )
        )

        embedding_time = (
            time.perf_counter()
            - embedding_start
        )

        # -------------------------------------------------
        # 2. CHROMA SEARCH
        # -------------------------------------------------
        chroma_start = (
            time.perf_counter()
        )

        result = self.collection.query(
            query_embeddings=[
                query_embedding
            ],
            n_results=top_k,
            include=[
                "documents",
                "metadatas",
                "distances",
            ],
        )

        chroma_time = (
            time.perf_counter()
            - chroma_start
        )

        # -------------------------------------------------
        # 3. FORMAT + DISTANCE FILTER
        # -------------------------------------------------
        matches = self._format_results(
            result
        )

        total_time = (
            time.perf_counter()
            - total_start
        )

        # -------------------------------------------------
        # DEBUG
        # -------------------------------------------------
        raw_count = len(
            result.get(
                "ids",
                [[]],
            )[0]
        )

        print()
        print("=" * 70)

        print(
            "[RETRIEVAL] Soru:",
            clean_query,
        )

        print(
            "[RETRIEVAL] İstenen top_k:",
            top_k,
        )

        print(
            "[RETRIEVAL] Ham sonuç:",
            raw_count,
        )

        print(
            "[RETRIEVAL] Distance sonrası:",
            len(matches),
        )

        print("-" * 70)

        for index, match in enumerate(
            matches,
            start=1,
        ):
            metadata = match[
                "metadata"
            ]

            print(
                f"{index}. "
                f"{metadata.get('org', 'Bilinmiyor')} "
                f"{metadata.get('code', 'Bilinmiyor')} | "
                f"Clause: "
                f"{metadata.get('clause', 'Bilinmiyor')} | "
                f"Distance: "
                f"{match['distance']:.4f}"
            )

        print("-" * 70)

        print(
            f"[PERF] Embedding: "
            f"{embedding_time:.2f} sn"
        )

        print(
            f"[PERF] Chroma Search: "
            f"{chroma_time:.2f} sn"
        )

        print(
            f"[PERF] Retrieval Total: "
            f"{total_time:.2f} sn"
        )

        print("=" * 70)
        print()

        return matches