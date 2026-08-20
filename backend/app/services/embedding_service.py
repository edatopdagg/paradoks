from sentence_transformers import SentenceTransformer

from app.core.config import (
    EMBEDDING_MODEL_NAME,
    QUERY_PREFIX,
    PASSAGE_PREFIX,
)


class EmbeddingService:
    def __init__(self) -> None:
        self.model = SentenceTransformer(
            EMBEDDING_MODEL_NAME
        )

    def embed_query(
        self,
        query: str,
    ) -> list[float]:
        clean_query = (
            query
            or ""
        ).strip()

        if not clean_query:
            raise ValueError(
                "Embedding sorgusu boş olamaz."
            )

        prepared_query = (
            f"{QUERY_PREFIX}{clean_query}"
        )

        embedding = self.model.encode(
            prepared_query,
            normalize_embeddings=True,
        )

        return embedding.tolist()

    def embed_queries(
        self,
        queries: list[str],
    ) -> list[list[float]]:
        """
        Birden fazla retrieval sorgusunu
        tek batch içinde embed eder.

        QueryNormalizer tarafından üretilen
        teknik varyantlar için kullanılır.
        """

        if not queries:
            raise ValueError(
                "Embedding sorgu listesi boş olamaz."
            )

        prepared_queries: list[str] = []

        for query in queries:
            clean_query = (
                query
                or ""
            ).strip()

            if not clean_query:
                continue

            prepared_queries.append(
                f"{QUERY_PREFIX}{clean_query}"
            )

        if not prepared_queries:
            raise ValueError(
                "Geçerli embedding sorgusu bulunamadı."
            )

        embeddings = self.model.encode(
            prepared_queries,
            batch_size=min(
                8,
                len(prepared_queries),
            ),
            normalize_embeddings=True,
            show_progress_bar=False,
        )

        return embeddings.tolist()

    def embed_passage(
        self,
        passage: str,
    ) -> list[float]:
        clean_passage = (
            passage
            or ""
        ).strip()

        if not clean_passage:
            raise ValueError(
                "Embedding metni boş olamaz."
            )

        prepared_passage = (
            f"{PASSAGE_PREFIX}{clean_passage}"
        )

        embedding = self.model.encode(
            prepared_passage,
            normalize_embeddings=True,
        )

        return embedding.tolist()