"""
Embeds text chunks into vector representations and writes them
to the Vector Database.

Uses ChromaDB with intfloat/multilingual-e5-small.
"""

import hashlib
from pathlib import Path

import chromadb
from sentence_transformers import SentenceTransformer
from tqdm import tqdm

from models import Chunk, DocStatus


EMBEDDING_BATCH_SIZE = 8
UPSERT_BATCH_SIZE = 256
EXISTENCE_CHECK_BATCH_SIZE = 500


class VectorStore:
    def __init__(
        self,
        db_path: str | Path,
        collection_name: str = "telecom_standards",
    ):
        self.collection_name = collection_name

        self.db_path = Path(db_path)

        self.db_path.mkdir(
            parents=True,
            exist_ok=True,
        )

        print(
            f"[VECTOR] DB yolu: "
            f"{self.db_path.resolve()}"
        )

        self.client = chromadb.PersistentClient(
            path=str(self.db_path)
        )

        self.collection = (
            self.client.get_or_create_collection(
                collection_name
            )
        )

        print(
            "[VECTOR] Mevcut DB chunk sayısı:",
            self.collection.count(),
        )

        print(
            "[VECTOR] Embedding modeli yükleniyor..."
        )

        self.model = SentenceTransformer(
            "intfloat/multilingual-e5-small"
        )

    def embed(
        self,
        text: str,
    ) -> list[float]:
        """
        Tek bir metni E5 passage embedding'ine çevirir.
        """

        clean_text = (
            text or ""
        ).strip()

        formatted_text = (
            f"passage: {clean_text}"
        )

        return self.model.encode(
            formatted_text,
            normalize_embeddings=True,
        ).tolist()

    def _build_chunk_id(
        self,
        chunk: Chunk,
    ) -> str:
        """
        Aynı içerik ve metadata kombinasyonu için
        her çalıştırmada aynı deterministic ID üretir.
        """

        identity = "|".join(
            [
                (
                    chunk.doc_org
                    or ""
                ).strip(),
                (
                    chunk.doc_code
                    or ""
                ).strip(),
                (
                    chunk.version
                    or ""
                ).strip(),
                (
                    chunk.clause
                    or ""
                ).strip(),
                (
                    chunk.text
                    or ""
                ).strip(),
            ]
        )

        digest = hashlib.sha256(
            identity.encode("utf-8")
        ).hexdigest()

        return f"chunk_{digest}"

    def _prepare_unique_chunks(
        self,
        chunks: list[Chunk],
    ) -> list[tuple[str, Chunk]]:
        """
        VOID, boş ve aynı deterministic ID'ye sahip
        duplicate chunk'ları temizler.
        """

        unique_chunks: list[
            tuple[str, Chunk]
        ] = []

        seen_ids: set[str] = set()

        void_count = 0
        empty_count = 0
        duplicate_count = 0

        for chunk in chunks:
            if chunk.status == DocStatus.VOID:
                void_count += 1
                continue

            clean_text = (
                chunk.text
                or ""
            ).strip()

            if not clean_text:
                empty_count += 1
                continue

            chunk.text = clean_text

            chunk_id = (
                self._build_chunk_id(
                    chunk
                )
            )

            if chunk_id in seen_ids:
                duplicate_count += 1
                continue

            seen_ids.add(
                chunk_id
            )

            unique_chunks.append(
                (
                    chunk_id,
                    chunk,
                )
            )

        print(
            "[VECTOR] Gelen chunk:",
            len(chunks),
        )

        if void_count:
            print(
                "[VECTOR] VOID atlandı:",
                void_count,
            )

        if empty_count:
            print(
                "[VECTOR] Boş chunk atlandı:",
                empty_count,
            )

        if duplicate_count:
            print(
                "[VECTOR] Aynı doküman içi duplicate atlandı:",
                duplicate_count,
            )

        print(
            "[VECTOR] Unique geçerli chunk:",
            len(unique_chunks),
        )

        return unique_chunks

    def _remove_already_indexed_chunks(
        self,
        chunks: list[tuple[str, Chunk]],
    ) -> list[tuple[str, Chunk]]:
        """
        Resume sırasında ChromaDB'de zaten bulunan deterministic
        ID'leri tespit eder.

        Zaten DB'de bulunan chunk'lar yeniden embed edilmez.
        """

        if not chunks:
            return []

        all_ids = [
            chunk_id
            for chunk_id, _
            in chunks
        ]

        existing_ids: set[str] = set()

        for start in range(
            0,
            len(all_ids),
            EXISTENCE_CHECK_BATCH_SIZE,
        ):
            batch_ids = all_ids[
                start:
                start + EXISTENCE_CHECK_BATCH_SIZE
            ]

            result = self.collection.get(
                ids=batch_ids,
                include=[],
            )

            existing_ids.update(
                result.get(
                    "ids",
                    [],
                )
            )

        missing_chunks = [
            (
                chunk_id,
                chunk,
            )
            for chunk_id, chunk
            in chunks
            if chunk_id not in existing_ids
        ]

        if existing_ids:
            print(
                "[VECTOR] DB'de zaten vardı, atlandı:",
                len(existing_ids),
            )

        print(
            "[VECTOR] Yeni embed edilecek chunk:",
            len(missing_chunks),
        )

        return missing_chunks

    def upsert_chunks(
        self,
        chunks: list[Chunk],
    ) -> int:
        """
        Chunk'ları:

        1. VOID / boş / duplicate temizler.
        2. DB'de zaten bulunan deterministic ID'leri atlar.
        3. Sadece eksik chunk'ları embed eder.
        4. ChromaDB'ye batch halinde yazar.

        Bu yapı rebuild'in güvenli şekilde resume edilmesini sağlar.
        """

        # -------------------------------------------------
        # 1. VALIDATION + LOCAL DEDUP
        # -------------------------------------------------
        unique_chunks = (
            self._prepare_unique_chunks(
                chunks
            )
        )

        if not unique_chunks:
            return 0

        # -------------------------------------------------
        # 2. DB'DE ZATEN VAR MI?
        # -------------------------------------------------
        chunks_to_write = (
            self._remove_already_indexed_chunks(
                unique_chunks
            )
        )

        if not chunks_to_write:
            print(
                "[VECTOR] Bu dokümanın tüm chunk'ları "
                "zaten indexlenmiş."
            )
            return 0

        # -------------------------------------------------
        # 3. EMBEDDING
        # -------------------------------------------------
        formatted_texts = [
            f"passage: {chunk.text}"
            for _, chunk
            in chunks_to_write
        ]

        embeddings = self.model.encode(
            formatted_texts,
            batch_size=EMBEDDING_BATCH_SIZE,
            show_progress_bar=True,
            normalize_embeddings=True,
        ).tolist()

        # -------------------------------------------------
        # 4. CHROMA BATCH UPSERT
        # -------------------------------------------------
        written = 0

        for start in tqdm(
            range(
                0,
                len(chunks_to_write),
                UPSERT_BATCH_SIZE,
            ),
            desc="Chroma batch upsert",
            unit="batch",
        ):
            end = (
                start
                + UPSERT_BATCH_SIZE
            )

            batch_items = (
                chunks_to_write[
                    start:end
                ]
            )

            batch_embeddings = (
                embeddings[
                    start:end
                ]
            )

            ids: list[str] = []
            documents: list[str] = []
            metadatas: list[dict] = []

            for (
                chunk_id,
                chunk,
            ) in batch_items:
                ids.append(
                    chunk_id
                )

                documents.append(
                    chunk.text
                )

                status = (
                    chunk.status.value
                    if hasattr(
                        chunk.status,
                        "value",
                    )
                    else str(
                        chunk.status
                    )
                )

                metadatas.append(
                    {
                        "org": (
                            chunk.doc_org
                            or ""
                        ),
                        "code": (
                            chunk.doc_code
                            or ""
                        ),
                        "version": (
                            chunk.version
                            or "Latest"
                        ),
                        "clause": (
                            chunk.clause
                            or ""
                        ),
                        "clause_title": (
                            chunk.clause_title
                            or ""
                        ),
                        "status": status,
                        "source_url": (
                            chunk.source_url
                            or ""
                        ),
                    }
                )

            if len(ids) != len(set(ids)):
                raise RuntimeError(
                    "Chroma upsert öncesi batch içinde "
                    "duplicate chunk ID tespit edildi."
                )

            self.collection.upsert(
                ids=ids,
                embeddings=batch_embeddings,
                documents=documents,
                metadatas=metadatas,
            )

            written += len(
                batch_items
            )

        return written
