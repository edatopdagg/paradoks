from typing import Any

from sentence_transformers import CrossEncoder

from app.core.config import (
    RERANKER_MAX_LENGTH,
    RERANKER_MODEL_NAME,
    RERANKER_TOP_K,
)


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
            raise ValueError("Yeniden sıralama sorusu boş olamaz.")

        if not candidates:
            return []

        query_document_pairs = [
            [clean_query, candidate["text"]]
            for candidate in candidates
        ]

        scores = self.model.predict(
            query_document_pairs,
            batch_size=1,
            show_progress_bar=False,
        )

        ranked_candidates: list[dict[str, Any]] = []

        for candidate, score in zip(candidates, scores):
            ranked_candidate = candidate.copy()
            ranked_candidate["rerank_score"] = float(score)
            ranked_candidates.append(ranked_candidate)

        ranked_candidates.sort(
            key=lambda candidate: candidate["rerank_score"],
            reverse=True,
        )

        return ranked_candidates[:top_k]