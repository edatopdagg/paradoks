import sqlite3
from pathlib import Path
from typing import Any

from app.core.config import (
    PRIORITY_CATALOG_PATH,
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


def _get_source_clause_from_catalog(
    *,
    version_id: str,
    clause_id: str,
    catalog_path: Path,
) -> dict[str, Any] | None:

    if not catalog_path.is_file():
        return None

    connection = sqlite3.connect(
        _read_only_uri(
            catalog_path
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
        return None

    return dict(row)


def get_source_clause(
    *,
    version_id: str,
    clause_id: str,
    catalog_path: str | Path | None = None,
) -> dict[str, Any]:

    # Explicit catalog istendiyse yaln?zca onu kullan.
    if catalog_path is not None:

        resolved_path = Path(
            catalog_path
        )

        if not resolved_path.is_file():
            raise FileNotFoundError(
                str(resolved_path)
            )

        result = (
            _get_source_clause_from_catalog(
                version_id=version_id,
                clause_id=clause_id,
                catalog_path=resolved_path,
            )
        )

        if result is None:
            raise KeyError(
                (
                    version_id,
                    clause_id,
                )
            )

        return result

    # --------------------------------------------------
    # NORMAL RUNTIME
    #
    # 1. Ana V3 katalog
    # 2. Priority/front-shelf katalog
    # --------------------------------------------------

    catalog_paths = [
        Path(V3_CATALOG_PATH),
    ]

    if PRIORITY_CATALOG_PATH:
        priority_path = Path(
            PRIORITY_CATALOG_PATH
        )

        if (
            priority_path
            not in catalog_paths
        ):
            catalog_paths.append(
                priority_path
            )

    existing_catalog = False

    for resolved_path in catalog_paths:

        if not resolved_path.is_file():
            continue

        existing_catalog = True

        result = (
            _get_source_clause_from_catalog(
                version_id=version_id,
                clause_id=clause_id,
                catalog_path=resolved_path,
            )
        )

        if result is not None:

            print(
                "[SOURCE] Clause resolved from:",
                resolved_path,
            )

            return result

    if not existing_catalog:
        raise FileNotFoundError(
            ", ".join(
                str(path)
                for path in catalog_paths
            )
        )

    raise KeyError(
        (
            version_id,
            clause_id,
        )
    )
