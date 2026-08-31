import hashlib
import re
import sqlite3
from pathlib import Path
from typing import Any


def _normalize(value: str) -> str:
    return re.sub(
        r"\s+",
        " ",
        (value or "").strip(),
    ).casefold()


def _stable_id(
    prefix: str,
    *parts: str,
) -> str:
    identity = "|".join(
        _normalize(part)
        for part in parts
    )

    digest = hashlib.sha256(
        identity.encode("utf-8")
    ).hexdigest()[:24]

    return f"{prefix}_{digest}"


class V3Catalog:
    def __init__(
        self,
        database_path: str | Path,
    ):
        self.database_path = Path(
            database_path
        )

        self.database_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.connection = sqlite3.connect(
            str(self.database_path)
        )

        self.connection.row_factory = (
            sqlite3.Row
        )

        self.connection.execute(
            "PRAGMA foreign_keys = ON"
        )

        self._create_schema()

    def _create_schema(self) -> None:
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS documents (
                id TEXT PRIMARY KEY,
                org TEXT NOT NULL,
                code TEXT NOT NULL,
                org_key TEXT NOT NULL,
                code_key TEXT NOT NULL,
                title TEXT NOT NULL DEFAULT '',
                UNIQUE(org_key, code_key)
            );

            CREATE TABLE IF NOT EXISTS document_versions (
                id TEXT PRIMARY KEY,
                document_id TEXT NOT NULL,
                version TEXT NOT NULL,
                release TEXT NOT NULL DEFAULT '',
                source_url TEXT NOT NULL DEFAULT '',
                local_path TEXT NOT NULL DEFAULT '',
                content_sha256 TEXT NOT NULL DEFAULT '',
                is_latest INTEGER NOT NULL DEFAULT 1,
                FOREIGN KEY(document_id)
                    REFERENCES documents(id),
                UNIQUE(document_id, version)
            );

            CREATE TABLE IF NOT EXISTS clauses (
                id TEXT PRIMARY KEY,
                version_id TEXT NOT NULL,
                number TEXT NOT NULL,
                title TEXT NOT NULL DEFAULT '',
                body_text TEXT NOT NULL DEFAULT '',
                page_start INTEGER,
                page_end INTEGER,
                FOREIGN KEY(version_id)
                    REFERENCES document_versions(id),
                UNIQUE(version_id, number)
            );

            CREATE TABLE IF NOT EXISTS chunks (
                id TEXT PRIMARY KEY,
                clause_id TEXT NOT NULL,
                chunk_index INTEGER NOT NULL,
                text TEXT NOT NULL,
                char_start INTEGER NOT NULL DEFAULT 0,
                char_end INTEGER NOT NULL DEFAULT 0,
                content_sha256 TEXT NOT NULL,
                FOREIGN KEY(clause_id)
                    REFERENCES clauses(id),
                UNIQUE(clause_id, chunk_index)
            );

            CREATE TABLE IF NOT EXISTS reference_edges (
                id TEXT PRIMARY KEY,
                source_version_id TEXT NOT NULL,
                source_clause_id TEXT,
                target_document_id TEXT,
                target_org TEXT NOT NULL,
                target_code TEXT NOT NULL,
                ref_number INTEGER,
                raw_text TEXT NOT NULL DEFAULT '',
                FOREIGN KEY(source_version_id)
                    REFERENCES document_versions(id),
                FOREIGN KEY(source_clause_id)
                    REFERENCES clauses(id),
                FOREIGN KEY(target_document_id)
                    REFERENCES documents(id)
            );

            CREATE INDEX IF NOT EXISTS
                idx_versions_document
                ON document_versions(document_id);

            CREATE INDEX IF NOT EXISTS
                idx_clauses_version
                ON clauses(version_id);

            CREATE INDEX IF NOT EXISTS
                idx_chunks_clause
                ON chunks(clause_id);

            CREATE INDEX IF NOT EXISTS
                idx_edges_source
                ON reference_edges(source_version_id);

            CREATE INDEX IF NOT EXISTS
                idx_edges_target
                ON reference_edges(
                    target_org,
                    target_code
                );
            """
        )

        self.connection.commit()

    def close(self) -> None:
        self.connection.close()

    def upsert_document(
        self,
        *,
        org: str,
        code: str,
        title: str,
    ) -> str:
        org_value = re.sub(
            r"\s+",
            " ",
            org.strip(),
        ).upper()

        code_value = re.sub(
            r"\s+",
            " ",
            code.strip(),
        ).upper()

        org_key = _normalize(
            org_value
        )

        code_key = _normalize(
            code_value
        )

        document_id = _stable_id(
            "doc",
            org_key,
            code_key,
        )

        self.connection.execute(
            """
            INSERT INTO documents(
                id,
                org,
                code,
                org_key,
                code_key,
                title
            )
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(org_key, code_key)
            DO UPDATE SET
                title = CASE
                    WHEN excluded.title <> ''
                    THEN excluded.title
                    ELSE documents.title
                END
            """,
            (
                document_id,
                org_value,
                code_value,
                org_key,
                code_key,
                title.strip(),
            ),
        )

        self.connection.commit()

        return document_id

    def upsert_version(
        self,
        *,
        document_id: str,
        version: str,
        release: str,
        source_url: str,
        local_path: str,
        content_sha256: str = "",
        is_latest: bool = True,
    ) -> str:
        version_value = version.strip()

        version_id = _stable_id(
            "ver",
            document_id,
            version_value,
        )

        self.connection.execute(
            """
            INSERT INTO document_versions(
                id,
                document_id,
                version,
                release,
                source_url,
                local_path,
                content_sha256,
                is_latest
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(document_id, version)
            DO UPDATE SET
                release = excluded.release,
                source_url = excluded.source_url,
                local_path = excluded.local_path,
                content_sha256 =
                    excluded.content_sha256,
                is_latest = excluded.is_latest
            """,
            (
                version_id,
                document_id,
                version_value,
                release.strip(),
                source_url.strip(),
                local_path.strip(),
                content_sha256.strip(),
                int(is_latest),
            ),
        )

        self.connection.commit()

        return version_id

    def upsert_clause(
        self,
        *,
        version_id: str,
        number: str,
        title: str,
        body_text: str,
        page_start: int | None,
        page_end: int | None,
    ) -> str:
        number_value = number.strip()

        clause_id = _stable_id(
            "clause",
            version_id,
            number_value,
        )

        self.connection.execute(
            """
            INSERT INTO clauses(
                id,
                version_id,
                number,
                title,
                body_text,
                page_start,
                page_end
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(version_id, number)
            DO UPDATE SET
                title = excluded.title,
                body_text = excluded.body_text,
                page_start = excluded.page_start,
                page_end = excluded.page_end
            """,
            (
                clause_id,
                version_id,
                number_value,
                title.strip(),
                body_text.strip(),
                page_start,
                page_end,
            ),
        )

        self.connection.commit()

        return clause_id

    def upsert_chunk(
        self,
        *,
        clause_id: str,
        text: str,
        chunk_index: int,
        char_start: int,
        char_end: int,
    ) -> str:
        clean_text = text.strip()

        chunk_id = _stable_id(
            "chunk",
            clause_id,
            str(chunk_index),
        )

        content_sha256 = hashlib.sha256(
            clean_text.encode("utf-8")
        ).hexdigest()

        self.connection.execute(
            """
            INSERT INTO chunks(
                id,
                clause_id,
                chunk_index,
                text,
                char_start,
                char_end,
                content_sha256
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(clause_id, chunk_index)
            DO UPDATE SET
                text = excluded.text,
                char_start = excluded.char_start,
                char_end = excluded.char_end,
                content_sha256 =
                    excluded.content_sha256
            """,
            (
                chunk_id,
                clause_id,
                chunk_index,
                clean_text,
                char_start,
                char_end,
                content_sha256,
            ),
        )

        self.connection.commit()

        return chunk_id

    def upsert_reference(
        self,
        *,
        source_version_id: str,
        source_clause_id: str | None,
        target_document_id: str | None,
        target_org: str,
        target_code: str,
        ref_number: int | None,
        raw_text: str,
    ) -> str:
        target_org_value = re.sub(
            r"\s+",
            " ",
            target_org.strip(),
        ).upper()

        target_code_value = re.sub(
            r"\s+",
            " ",
            target_code.strip(),
        ).upper()

        edge_id = _stable_id(
            "edge",
            source_version_id,
            source_clause_id or "",
            target_org_value,
            target_code_value,
            str(ref_number or ""),
        )

        self.connection.execute(
            """
            INSERT INTO reference_edges(
                id,
                source_version_id,
                source_clause_id,
                target_document_id,
                target_org,
                target_code,
                ref_number,
                raw_text
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id)
            DO UPDATE SET
                target_document_id =
                    excluded.target_document_id,
                raw_text = excluded.raw_text
            """,
            (
                edge_id,
                source_version_id,
                source_clause_id,
                target_document_id,
                target_org_value,
                target_code_value,
                ref_number,
                raw_text.strip(),
            ),
        )

        self.connection.commit()

        return edge_id

    def get_source_locator(
        self,
        chunk_id: str,
    ) -> dict[str, Any] | None:
        row = self.connection.execute(
            """
            SELECT
                chunk.id AS source_id,
                document.id AS document_id,
                version.id AS version_id,
                clause.id AS clause_id,
                document.org,
                document.code,
                version.version,
                clause.number AS clause,
                clause.title AS clause_title,
                clause.page_start,
                clause.page_end,
                version.source_url,
                version.local_path,
                chunk.text AS highlight_text,
                chunk.char_start,
                chunk.char_end
            FROM chunks AS chunk
            JOIN clauses AS clause
                ON clause.id = chunk.clause_id
            JOIN document_versions AS version
                ON version.id = clause.version_id
            JOIN documents AS document
                ON document.id =
                    version.document_id
            WHERE chunk.id = ?
            """,
            (chunk_id,),
        ).fetchone()

        if row is None:
            return None

        result = dict(row)

        result["viewer_url"] = (
            f"/sources/{result['version_id']}"
            f"/clauses/{result['clause_id']}"
        )

        return result

    def list_references(
        self,
        source_version_id: str,
    ) -> list[dict[str, Any]]:
        rows = self.connection.execute(
            """
            SELECT *
            FROM reference_edges
            WHERE source_version_id = ?
            ORDER BY
                ref_number,
                target_org,
                target_code
            """,
            (source_version_id,),
        ).fetchall()

        return [
            dict(row)
            for row in rows
        ]