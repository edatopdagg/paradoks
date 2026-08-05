import chromadb

from app.core.config import (
    CHROMA_COLLECTION_NAME,
    CHROMA_DB_PATH,
)
from app.services.data_loader import load_chunks
from app.services.embedding_service import EmbeddingService


def main() -> None:
    chunks = load_chunks()
    embedding_service = EmbeddingService()

    client = chromadb.PersistentClient(
        path=str(CHROMA_DB_PATH)
    )

    collection = client.get_or_create_collection(
        name=CHROMA_COLLECTION_NAME
    )

    ids: list[str] = []
    documents: list[str] = []
    embeddings: list[list[float]] = []
    metadatas: list[dict] = []

    for chunk in chunks:
        ids.append(chunk["chunk_id"])
        documents.append(chunk["text"])

        embeddings.append(
            embedding_service.embed_passage(chunk["text"])
        )

        metadatas.append(
            {
                "org": chunk["org"],
                "code": chunk["code"],
                "version": chunk["version"],
                "clause": chunk["clause"],
                "status": chunk["status"],
                "source_url": chunk["source_url"],
            }
        )

    collection.upsert(
        ids=ids,
        documents=documents,
        embeddings=embeddings,
        metadatas=metadatas,
    )

    print(f"Yüklenen chunk sayısı: {len(chunks)}")
    print(f"Collection kayıt sayısı: {collection.count()}")
    print(f"DB konumu: {CHROMA_DB_PATH}")


if __name__ == "__main__":
    main()