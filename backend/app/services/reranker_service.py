from typing import Any

from sentence_transformers import CrossEncoder

from app.core.config import (
    RERANKER_MAX_LENGTH,
    RERANKER_MODEL_NAME,
    RERANKER_TOP_K,
)


# Yeni chunker yaklaşık 2400 karakter sınırı kullanıyor.
# Eski/veri tabanındaki büyük chunk'ların reranker'a
# kontrolsüz gitmesini engelle.
RERANKER_MAX_CHARS = 2600


class Reranker:
    def __init__(self) -> None:
        self.model = CrossEncoder(
            RERANKER_MODEL_NAME,
            max_length=RERANKER_MAX_LENGTH,
            device="cpu",
        )

    @staticmethod
    def _build_query_variants(
        original_query: str,
        candidate: dict[str, Any],
    ) -> list[str]:
        """
        Candidate'ın rerank edilmesinde kullanılacak
        query varyantlarını hazırlar.

        Kaynaklar:

        1. Orijinal kullanıcı sorgusu.
        2. Retriever tarafından bu candidate'ı bulan
           teknik query varyantları.

        Duplicate query'ler temizlenir.
        """

        variants: list[str] = []
        seen: set[str] = set()

        possible_queries = [
            original_query,
            *candidate.get(
                "matched_queries",
                [],
            ),
        ]

        for query in possible_queries:
            clean_query = (
                query
                or ""
            ).strip()

            if not clean_query:
                continue

            normalized = (
                clean_query.casefold()
            )

            if normalized in seen:
                continue

            seen.add(
                normalized
            )

            variants.append(
                clean_query
            )

        return variants

    def rerank(
        self,
        query: str,
        candidates: list[dict[str, Any]],
        top_k: int = RERANKER_TOP_K,
    ) -> list[dict[str, Any]]:
        """
        Retrieval adaylarını CrossEncoder ile
        yeniden sıralar.

        Önemli:

        Candidate yalnızca kullanıcının orijinal
        sorgusuyla skorlanmaz.

        Retriever tarafından candidate'ı bulan teknik
        query expansion'ları da kullanılır.

        Her candidate için elde edilen CrossEncoder
        skorlarından EN YÜKSEK olan final rerank score
        olarak kullanılır.

        Böylece doğal Türkçe bir sorgunun teknik standart
        terminolojisine çevrilmiş varyantı doğru kaynağı
        bulduysa, reranker bu bilgiyi kaybetmez.
        """

        clean_query = (
            query
            or ""
        ).strip()

        if not clean_query:
            raise ValueError(
                "Yeniden sıralama sorusu boş olamaz."
            )

        if top_k <= 0:
            raise ValueError(
                "top_k sıfırdan büyük olmalıdır."
            )

        if not candidates:
            return []

        # Tek aday varsa CrossEncoder çalıştırmaya
        # gerek yok.
        if len(candidates) == 1:
            ranked_candidate = (
                candidates[0].copy()
            )

            ranked_candidate[
                "rerank_score"
            ] = 1.0

            ranked_candidate[
                "rerank_query"
            ] = clean_query

            ranked_candidate[
                "rerank_variant_count"
            ] = 1

            return [
                ranked_candidate
            ]

        # -------------------------------------------------
        # 1. CANDIDATE HAZIRLAMA
        # -------------------------------------------------

        prepared_candidates: list[
            tuple[
                dict[str, Any],
                str,
                list[str],
            ]
        ] = []

        for candidate in candidates:
            text = (
                candidate.get(
                    "text"
                )
                or ""
            ).strip()

            if not text:
                continue

            if (
                len(text)
                > RERANKER_MAX_CHARS
            ):
                text = text[
                    :RERANKER_MAX_CHARS
                ]

            query_variants = (
                self._build_query_variants(
                    original_query=clean_query,
                    candidate=candidate,
                )
            )

            if not query_variants:
                continue

            prepared_candidates.append(
                (
                    candidate,
                    text,
                    query_variants,
                )
            )

        if not prepared_candidates:
            return []

        # -------------------------------------------------
        # 2. TÜM QUERY-CANDIDATE PAIR'LARI
        # -------------------------------------------------
        #
        # Bütün pair'ları tek predict çağrısına veriyoruz.
        # Böylece 4 ayrı CrossEncoder çağrısı yapmak yerine
        # batch inference kullanılır.
        # -------------------------------------------------

        query_document_pairs: list[
            list[str]
        ] = []

        pair_candidate_indexes: list[
            int
        ] = []

        pair_queries: list[
            str
        ] = []

        for candidate_index, (
            _,
            text,
            query_variants,
        ) in enumerate(
            prepared_candidates
        ):
            for query_variant in query_variants:
                query_document_pairs.append(
                    [
                        query_variant,
                        text,
                    ]
                )

                pair_candidate_indexes.append(
                    candidate_index
                )

                pair_queries.append(
                    query_variant
                )

        # -------------------------------------------------
        # 3. CROSS ENCODER
        # -------------------------------------------------

        scores = self.model.predict(
            query_document_pairs,
            batch_size=8,
            show_progress_bar=False,
        )

        # -------------------------------------------------
        # 4. HER CANDIDATE İÇİN EN İYİ SCORE
        # -------------------------------------------------

        best_scores = [
            float("-inf")
            for _ in prepared_candidates
        ]

        best_queries = [
            ""
            for _ in prepared_candidates
        ]

        for (
            score,
            candidate_index,
            query_variant,
        ) in zip(
            scores,
            pair_candidate_indexes,
            pair_queries,
        ):
            score_value = float(
                score
            )

            if (
                score_value
                > best_scores[
                    candidate_index
                ]
            ):
                best_scores[
                    candidate_index
                ] = score_value

                best_queries[
                    candidate_index
                ] = query_variant

        # -------------------------------------------------
        # 5. RESULT OLUŞTUR
        # -------------------------------------------------

        ranked_candidates: list[
            dict[str, Any]
        ] = []

        for candidate_index, (
            candidate,
            _,
            query_variants,
        ) in enumerate(
            prepared_candidates
        ):
            ranked_candidate = (
                candidate.copy()
            )

            ranked_candidate[
                "rerank_score"
            ] = best_scores[
                candidate_index
            ]

            ranked_candidate[
                "rerank_query"
            ] = best_queries[
                candidate_index
            ]

            ranked_candidate[
                "rerank_variant_count"
            ] = len(
                query_variants
            )

            ranked_candidates.append(
                ranked_candidate
            )

        # -------------------------------------------------
        # 6. FINAL SIRALAMA
        # -------------------------------------------------

        ranked_candidates.sort(
            key=lambda candidate: (
                candidate[
                    "rerank_score"
                ]
            ),
            reverse=True,
        )

        return ranked_candidates[
            :top_k
        ]