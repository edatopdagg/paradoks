import sqlite3
from pathlib import Path
from typing import Any


BACKEND_DIR = (
    Path(__file__)
    .resolve()
    .parents[2]
)

LEXICAL_DB_PATH = (
    BACKEND_DIR
    / "data"
    / "lexical_index.db"
)


class LexicalSearchService:
    """
    SQLite FTS5 tabanlı hızlı lexical retrieval.

    Bu servis ana semantic Retriever'ın yerine geçmez.

    Yalnızca semantic retrieval'ın yetersiz veya
    şüpheli kaldığı durumlarda kontrollü fallback
    olarak kullanılır.
    """

    def __init__(self) -> None:
        if not LEXICAL_DB_PATH.exists():
            raise FileNotFoundError(
                "Lexical index bulunamadı: "
                f"{LEXICAL_DB_PATH}"
            )

    def search_phrase(
        self,
        phrase: str,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """
        Verilen teknik ifadeyi FTS5 phrase query
        olarak arar.

        Örnek:

            E.164 number maximum length

            document defines version 1 of QUIC
        """

        clean_phrase = (
            phrase
            or ""
        ).strip()

        if not clean_phrase:
            return []

        if limit <= 0:
            return []

        # FTS5 phrase query.
        #
        # İçeride çift tırnak varsa kaçırıyoruz.
        escaped_phrase = (
            clean_phrase
            .replace(
                '"',
                '""',
            )
        )

        fts_query = (
            f'"{escaped_phrase}"'
        )

        connection = sqlite3.connect(
            str(LEXICAL_DB_PATH)
        )

        connection.row_factory = (
            sqlite3.Row
        )

        try:
            rows = connection.execute(
                """
                SELECT
                    chunk_id,
                    text,
                    org,
                    code,
                    version,
                    clause,
                    status,
                    source_url,
                    bm25(chunks_fts) AS lexical_score
                FROM chunks_fts
                WHERE chunks_fts MATCH ?
                ORDER BY lexical_score
                LIMIT ?
                """,
                (
                    fts_query,
                    limit,
                ),
            ).fetchall()

        finally:
            connection.close()

        results: list[
            dict[str, Any]
        ] = []

        for row in rows:
            status = (
                row["status"]
                or ""
            )

            if status not in {
                "available",
                "indexed",
            }:
                continue

            results.append(
                {
                    "chunk_id": (
                        row["chunk_id"]
                    ),
                    "text": (
                        row["text"]
                        or ""
                    ),
                    "metadata": {
                        "org": (
                            row["org"]
                            or ""
                        ),
                        "code": (
                            row["code"]
                            or ""
                        ),
                        "version": (
                            row["version"]
                            or ""
                        ),
                        "clause": (
                            row["clause"]
                            or ""
                        ),
                        "status": status,
                        "source_url": (
                            row["source_url"]
                            or ""
                        ),
                    },

                    # Semantic distance yok.
                    "distance": 0.0,

                    "lexical_score": (
                        float(
                            row[
                                "lexical_score"
                            ]
                        )
                    ),
                }
            )

        return results