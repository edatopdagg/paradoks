from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from app.core.config import (
    V3_CATALOG_PATH,
)


def _read_only_uri(
    catalog_path: Path,
) -> str:
    return (
        catalog_path
        .resolve()
        .as_uri()
        + "?mode=ro"
    )


def get_source_clause(
    *,
    version_id: str,
    clause_id: str,
    catalog_path: str | Path | None = None,
) -> dict[str, Any]:
    resolved_path = Path(
        catalog_path
        if catalog_path is not None
        else V3_CATALOG_PATH
    )

    if not resolved_path.is_file():
        raise FileNotFoundError(
            str(resolved_path)
        )

    connection = sqlite3.connect(
        _read_only_uri(
            resolved_path
        ),
        uri=True,
    )

    connection.row_factory = (
        sqlite3.Row
    )

    try:
        row = connection.execute(
            """
            SELECT
                document.id
                    AS document_id,
                version.id
                    AS version_id,
                clause.id
                    AS clause_id,

                document.org
                    AS org,
                document.code
                    AS code,
                document.title
                    AS document_title,

                version.version
                    AS version,
                version.release
                    AS release,

                clause.number
                    AS clause,
                clause.title
                    AS clause_title,
                clause.body_text
                    AS body_text,

                clause.page_start
                    AS page_start,
                clause.page_end
                    AS page_end,

                version.source_url
                    AS source_url,
                version.local_path
                    AS local_path

            FROM clauses AS clause

            JOIN document_versions AS version
                ON version.id =
                   clause.version_id

            JOIN documents AS document
                ON document.id =
                   version.document_id

            WHERE
                version.id = ?
                AND clause.id = ?

            LIMIT 1
            """,
            (
                version_id.strip(),
                clause_id.strip(),
            ),
        ).fetchone()

    finally:
        connection.close()

    if row is None:
        raise KeyError(
            (
                version_id,
                clause_id,
            )
        )

    return dict(
        row
    )
