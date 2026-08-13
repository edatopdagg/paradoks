import sqlite3
from pathlib import Path

import chromadb

from app.core.config import (
    CHROMA_COLLECTION_NAME,
    CHROMA_DB_PATH,
)


BACKEND_DIR = Path(__file__).resolve().parents[1]
LEXICAL_DB_PATH = BACKEND_DIR / "data" / "lexical_index.db"

BATCH_SIZE = 1000


def build_lexical_index() -> None:
    print("[LEXICAL] Chroma ba─şlant─▒s─▒ kuruluyor...")

    client = chromadb.PersistentClient(
        path=str(CHROMA_DB_PATH)
    )

    collection = client.get_collection(
        name=CHROMA_COLLECTION_NAME
    )

    total_chunks = collection.count()

    print(
        f"[LEXICAL] Chroma toplam chunk: "
        f"{total_chunks}"
    )

    # data klas├Âr├╝ yoksa olu┼ştur.
    LEXICAL_DB_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    connection = sqlite3.connect(
        str(LEXICAL_DB_PATH)
    )

    cursor = connection.cursor()

    # Her build i┼şleminde indexi s─▒f─▒rdan kuruyoruz.
    cursor.execute(
        "DROP TABLE IF EXISTS chunks_fts"
    )

    cursor.execute(
        """
        CREATE VIRTUAL TABLE chunks_fts
        USING fts5(
            chunk_id UNINDEXED,
            text,
            org UNINDEXED,
            code UNINDEXED,
            version UNINDEXED,
            clause UNINDEXED,
            status UNINDEXED,
            source_url UNINDEXED
        )
        """
    )

    indexed_count = 0

    for offset in range(
        0,
        total_chunks,
        BATCH_SIZE,
    ):
        result = collection.get(
            limit=BATCH_SIZE,
            offset=offset,
            include=[
                "documents",
                "metadatas",
            ],
        )

        ids = result["ids"]
        documents = result["documents"]
        metadatas = result["metadatas"]

        rows = []

        for chunk_id, document, metadata in zip(
            ids,
            documents,
            metadatas,
        ):
            metadata = metadata or {}

            rows.append(
                (
                    chunk_id,
                    document or "",
                    str(
                        metadata.get(
                            "org",
                            "",
                        )
                        or ""
                    ),
                    str(
                        metadata.get(
                            "code",
                            "",
                        )
                        or ""
                    ),
                    str(
                        metadata.get(
                            "version",
                            "",
                        )
                        or ""
                    ),
                    str(
                        metadata.get(
                            "clause",
                            "",
                        )
                        or ""
                    ),
                    str(
                        metadata.get(
                            "status",
                            "",
                        )
                        or ""
                    ),
                    str(
                        metadata.get(
                            "source_url",
                            "",
                        )
                        or ""
                    ),
                )
            )

        cursor.executemany(
            """
            INSERT INTO chunks_fts(
                chunk_id,
                text,
                org,
                code,
                version,
                clause,
                status,
                source_url
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )

        connection.commit()

        indexed_count += len(rows)

        print(
            f"[LEXICAL] "
            f"{indexed_count}/{total_chunks} "
            f"chunk indexlendi."
        )

    connection.close()

    print()
    print("=" * 60)
    print("[LEXICAL] FTS5 index olu┼şturuldu.")
    print(
        f"[LEXICAL] Indexlenen chunk: "
        f"{indexed_count}"
    )
    print(
        f"[LEXICAL] Dosya: "
        f"{LEXICAL_DB_PATH}"
    )
    print("=" * 60)


if __name__ == "__main__":
    build_lexical_index()
