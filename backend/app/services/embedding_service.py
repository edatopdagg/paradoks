from sentence_transformers import SentenceTransformer

from app.core.config import (
    EMBEDDING_MODEL_NAME,
    QUERY_PREFIX,
    PASSAGE_PREFIX,
)


class EmbeddingService:
    def __init__(self) -> None:
        self.model = SentenceTransformer(EMBEDDING_MODEL_NAME)

    def embed_query(self, query: str) -> list[float]:
        prepared_query = f"{QUERY_PREFIX}{query.strip()}"

        embedding = self.model.encode(
            prepared_query,
            normalize_embeddings=True
        )

        return embedding.tolist()

    def embed_passage(self, passage: str) -> list[float]:
        prepared_passage = f"{PASSAGE_PREFIX}{passage.strip()}"

        embedding = self.model.encode(
            prepared_passage,
            normalize_embeddings=True
        )

        return embedding.tolist()