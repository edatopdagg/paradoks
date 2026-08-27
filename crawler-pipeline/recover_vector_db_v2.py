import sqlite3
from pathlib import Path

import chromadb
from sentence_transformers import SentenceTransformer
from tqdm import tqdm


SOURCE_SQLITE = Path(
    r"C:\Users\edato\OneDrive\Masaüstü\paradoks-main"
    r"\crawler-pipeline\backend\vector_db_v2\chroma.sqlite3"
)

TARGET_DB = Path(
    r"C:\Users\edato\OneDrive\Masaüstü\paradoks-main"
    r"\crawler-pipeline\backend\vector_db_v2_recovered"
)

COLLECTION_NAME = "telecom_standards"
MODEL_NAME = "intfloat/multilingual-e5-small"

READ_BATCH_SIZE = 500
EMBED_BATCH_SIZE = 8
UPSERT_BATCH_SIZE = 256


def read_chunk_rows():
    connection = sqlite3.connect(SOURCE_SQLITE)
    cursor = connection.cursor()

    rows = cursor.execute(
        """
        SELECT
            e.id,
            e.embedding_id
        FROM embeddings e
        ORDER BY e.id
        """
    ).fetchall()

    total = len(rows)

    print("Kurtarılacak kayıt:", total)

    for start in range(0, total, READ_BATCH_SIZE):
        batch = rows[start:start + READ_BATCH_SIZE]

        recovered = []

        for internal_id, embedding_id in batch:
            metadata_rows = cursor.execute(
                """
                SELECT
                    key,
                    string_value,
                    int_value,
                    float_value,
                    bool_value
                FROM embedding_metadata
                WHERE id = ?
                """,
                (internal_id,),
            ).fetchall()

            metadata = {}
            document = ""

            for (
                key,
                string_value,
                int_value,
                float_value,
                bool_value,
            ) in metadata_rows:

                if key == "chroma:document":
                    document = string_value or ""
                    continue

                if string_value is not None:
                    metadata[key] = string_value

                elif int_value is not None:
                    metadata[key] = int_value

                elif float_value is not None:
                    metadata[key] = float_value

                elif bool_value is not None:
                    metadata[key] = bool(bool_value)

            document = document.strip()

            if not document:
                print(
                    "[SKIP] Doküman metni yok:",
                    embedding_id,
                )
                continue

            recovered.append(
                (
                    embedding_id,
                    document,
                    metadata,
                )
            )

        yield recovered

    connection.close()


def main():
    print("=" * 70)
    print("PARADOKS VECTOR DB V2 RECOVERY")
    print("=" * 70)

    print("Kaynak SQLite:", SOURCE_SQLITE)
    print("Hedef DB:", TARGET_DB)

    if not SOURCE_SQLITE.exists():
        raise SystemExit(
            "Kaynak chroma.sqlite3 bulunamadı."
        )

    if TARGET_DB.exists():
        raise SystemExit(
            "Hedef recovery DB zaten var. "
            "Silmeden tekrar çalıştırma."
        )

    TARGET_DB.mkdir(
        parents=True,
        exist_ok=True,
    )

    print()
    print("Embedding modeli yükleniyor...")

    model = SentenceTransformer(
        MODEL_NAME
    )

    client = chromadb.PersistentClient(
        path=str(TARGET_DB)
    )

    collection = client.get_or_create_collection(
        COLLECTION_NAME
    )

    written_total = 0

    for recovered_batch in read_chunk_rows():
        if not recovered_batch:
            continue

        ids = [
            item[0]
            for item in recovered_batch
        ]

        documents = [
            item[1]
            for item in recovered_batch
        ]

        metadatas = [
            item[2]
            for item in recovered_batch
        ]

        formatted_documents = [
            f"passage: {document}"
            for document in documents
        ]

        embeddings = model.encode(
            formatted_documents,
            batch_size=EMBED_BATCH_SIZE,
            show_progress_bar=True,
            normalize_embeddings=True,
        ).tolist()

        for start in tqdm(
            range(
                0,
                len(ids),
                UPSERT_BATCH_SIZE,
            ),
            desc="Recovery upsert",
            unit="batch",
        ):
            end = (
                start
                + UPSERT_BATCH_SIZE
            )

            collection.upsert(
                ids=ids[start:end],
                embeddings=embeddings[start:end],
                documents=documents[start:end],
                metadatas=metadatas[start:end],
            )

        written_total += len(ids)

        print(
            "[RECOVERY] Yazılan:",
            written_total,
            "| DB toplam:",
            collection.count(),
        )

    print()
    print("=" * 70)
    print("RECOVERY TAMAMLANDI")
    print("=" * 70)
    print(
        "Final chunk:",
        collection.count(),
    )
    print(
        "Yeni DB:",
        TARGET_DB.resolve(),
    )


if __name__ == "__main__":
    main()
