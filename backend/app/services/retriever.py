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

    def search(
        self,
        query: str,
        top_k: int = 3,
    ) -> list[dict[str, Any]]:
        clean_query = query.strip()

        if not clean_query:
            raise ValueError("Arama sorusu boş olamaz.")

        query_embedding = self.embedding_service.embed_query(
            clean_query
        )

        result = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            include=[
                "documents",
                "metadatas",
                "distances",
            ],
        )

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
               "metadata": metadata,
               "distance": distance,
        }
    )

        return matches