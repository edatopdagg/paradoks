import argparse
import sqlite3
from pathlib import Path


def normalize(value: str) -> str:
    return " ".join((value or "").split()).casefold()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--catalog", required=True)
    parser.add_argument("--output-db", required=True)
    parser.add_argument("--collection", default="telecom_standards_v3")
    parser.add_argument("--smoke-query", required=True)
    args = parser.parse_args()

    import chromadb
    from sentence_transformers import SentenceTransformer

    catalog_path = Path(args.catalog).resolve()
    output_db = Path(args.output_db).resolve()
    output_db.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(str(catalog_path))
    connection.row_factory = sqlite3.Row
    rows = connection.execute(
        """
        SELECT
            chunk.id AS source_id,
            chunk.text,
            chunk.char_start,
            chunk.char_end,
            document.id AS document_id,
            document.org,
            document.code,
            version.id AS version_id,
            version.version,
            version.release,
            version.source_url,
            version.local_path,
            clause.id AS clause_id,
            clause.number AS clause,
            clause.title AS clause_title,
            clause.page_start,
            clause.page_end
        FROM chunks AS chunk
        JOIN clauses AS clause ON clause.id = chunk.clause_id
        JOIN document_versions AS version ON version.id = clause.version_id
        JOIN documents AS document ON document.id = version.document_id
        ORDER BY clause.number, chunk.chunk_index
        """
    ).fetchall()
    connection.close()

    content_rows = [
        row
        for row in rows
        if normalize(row["text"])
        and normalize(row["text"]) != normalize(row["clause_title"])
    ]
    skipped = len(rows) - len(content_rows)

    print("Catalog:", catalog_path)
    print("Vector DB:", output_db)
    print("Catalog chunk:", len(rows))
    print("Skipped heading-only:", skipped)
    print("Content chunk:", len(content_rows))

    client = chromadb.PersistentClient(path=str(output_db))
    collection = client.get_or_create_collection(args.collection)
    print("Existing vector:", collection.count())

    model = SentenceTransformer("intfloat/multilingual-e5-small")
    batch_size = 128
    written = 0

    for start in range(0, len(content_rows), batch_size):
        batch = content_rows[start : start + batch_size]
        texts = [row["text"] for row in batch]
        embeddings = model.encode(
            [f"passage: {text}" for text in texts],
            batch_size=32,
            normalize_embeddings=True,
            show_progress_bar=False,
        ).tolist()

        metadatas = []
        for row in batch:
            metadatas.append(
                {
                    "source_id": row["source_id"],
                    "document_id": row["document_id"],
                    "version_id": row["version_id"],
                    "clause_id": row["clause_id"],
                    "org": row["org"],
                    "code": row["code"],
                    "version": row["version"],
                    "release": row["release"],
                    "clause": row["clause"],
                    "clause_title": row["clause_title"],
                    "page_start": row["page_start"] if row["page_start"] is not None else -1,
                    "page_end": row["page_end"] if row["page_end"] is not None else -1,
                    "source_url": row["source_url"],
                    "local_path": row["local_path"],
                    "viewer_url": (
                        f"/sources/{row['version_id']}"
                        f"/clauses/{row['clause_id']}"
                    ),
                    "char_start": row["char_start"],
                    "char_end": row["char_end"],
                    "status": "indexed",
                }
            )

        collection.upsert(
            ids=[row["source_id"] for row in batch],
            documents=texts,
            embeddings=embeddings,
            metadatas=metadatas,
        )
        written += len(batch)
        print(f"Indexed: {written}/{len(content_rows)}")

    print("Final vector count:", collection.count())

    query_embedding = model.encode(
        f"query: {args.smoke_query}",
        normalize_embeddings=True,
    ).tolist()
    result = collection.query(
        query_embeddings=[query_embedding],
        n_results=min(5, collection.count()),
        include=["documents", "metadatas", "distances"],
    )

    print("\nSMOKE QUERY:", args.smoke_query)
    for index, metadata in enumerate(result["metadatas"][0], start=1):
        print(
            f"{index}. {metadata['org']} {metadata['code']} | "
            f"V{metadata['version']} | Madde {metadata['clause']} | "
            f"{metadata['clause_title']} | "
            f"distance={result['distances'][0][index - 1]:.4f}"
        )
        print("   viewer:", metadata["viewer_url"])
        print("   text:", result["documents"][0][index - 1][:240])


if __name__ == "__main__":
    main()
