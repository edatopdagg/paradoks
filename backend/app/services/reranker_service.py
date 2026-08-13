from typing import Any

from sentence_transformers import CrossEncoder

from app.core.config import (
    RERANKER_MAX_LENGTH,
    RERANKER_MODEL_NAME,
    RERANKER_TOP_K,
)


# Yeni chunker zaten yaklaşık 2400 karakter sınırı kullanıyor.
# Eski DB ile çalışırken de reranker'a devasa metin gitmesini engelle.
RERANKER_MAX_CHARS = 2600


class Reranker:
    def __init__(self) -> None:
        self.model = CrossEncoder(
            RERANKER_MODEL_NAME,
            max_length=RERANKER_MAX_LENGTH,
            device="cpu",
        )

    def rerank(
        self,
        query: str,
        candidates: list[dict[str, Any]],
        top_k: int = RERANKER_TOP_K,
    ) -> list[dict[str, Any]]:
        clean_query = query.strip()

        if not clean_query:
            raise ValueError(
                "Yeniden sıralama sorusu boş olamaz."
            )

        if not candidates:
            return []

        # Tek aday varsa model çalıştırmaya gerek yok.
        if len(candidates) == 1:
            ranked_candidate = candidates[0].copy()
            ranked_candidate["rerank_score"] = 1.0
            return [ranked_candidate]

        prepared_candidates: list[
            tuple[dict[str, Any], str]
        ] = []

        for candidate in candidates:
            text = (
                candidate.get("text")
                or ""
            ).strip()

            if not text:
                continue

            if len(text) > RERANKER_MAX_CHARS:
                text = text[
                    :RERANKER_MAX_CHARS
                ]

            prepared_candidates.append(
                (
                    candidate,
                    text,
                )
            )

        if not prepared_candidates:
            return []

        query_document_pairs = [
            [
                clean_query,
                text,
            ]
            for candidate, text
            in prepared_candidates
        ]

        scores = self.model.predict(
            query_document_pairs,
            batch_size=1,
            show_progress_bar=False,
        )

        ranked_candidates: list[
            dict[str, Any]
        ] = []

        for (
            candidate,
            _
        ), score in zip(
            prepared_candidates,
            scores,
        ):
            ranked_candidate = (
                candidate.copy()
            )

            ranked_candidate[
                "rerank_score"
            ] = float(score)

            ranked_candidates.append(
                ranked_candidate
            )

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