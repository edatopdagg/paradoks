"""V3 katalog üzerinde kalıcı ve devam edebilir tarama kuyruğu."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from v3_catalog import V3Catalog


VALID_STATUSES = {
    "pending",
    "fetching",
    "indexed",
    "blocked",
    "unresolved",
    "failed",
}


@dataclass(frozen=True)
class CrawlJob:
    document_id: str
    org: str
    code: str
    title: str
    depth: int
    status: str
    attempts: int
    discovered_from_edge_id: str | None


class V3CrawlQueue:
    def __init__(
        self,
        catalog: V3Catalog,
    ):
        self.catalog = catalog
        self.connection = catalog.connection
        self._create_schema()

    def _create_schema(self) -> None:
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS crawl_jobs (
                document_id TEXT PRIMARY KEY,
                depth INTEGER NOT NULL DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'pending',
                attempts INTEGER NOT NULL DEFAULT 0,
                discovered_from_edge_id TEXT,
                source_url TEXT NOT NULL DEFAULT '',
                last_error TEXT NOT NULL DEFAULT '',
                updated_at TEXT NOT NULL
                    DEFAULT CURRENT_TIMESTAMP,

                FOREIGN KEY(document_id)
                    REFERENCES documents(id),

                FOREIGN KEY(discovered_from_edge_id)
                    REFERENCES reference_edges(id)
            );

            CREATE INDEX IF NOT EXISTS
                idx_crawl_jobs_status_depth
            ON crawl_jobs(
                status,
                depth,
                document_id
            );
            """
        )

        self.connection.commit()

    def enqueue_document(
        self,
        *,
        document_id: str,
        depth: int,
        discovered_from_edge_id: str | None = None,
    ) -> None:
        if depth < 0:
            raise ValueError(
                "depth negatif olamaz."
            )

        has_version = self.connection.execute(
            """
            SELECT 1
            FROM document_versions
            WHERE document_id = ?
            LIMIT 1
            """,
            (document_id,),
        ).fetchone()

        initial_status = (
            "indexed"
            if has_version
            else "pending"
        )

        self.connection.execute(
            """
            INSERT INTO crawl_jobs(
                document_id,
                depth,
                status,
                discovered_from_edge_id
            )
            VALUES (?, ?, ?, ?)

            ON CONFLICT(document_id)
            DO UPDATE SET
                depth = MIN(
                    crawl_jobs.depth,
                    excluded.depth
                ),

                discovered_from_edge_id =
                    COALESCE(
                        crawl_jobs
                            .discovered_from_edge_id,
                        excluded
                            .discovered_from_edge_id
                    ),

                updated_at =
                    CURRENT_TIMESTAMP
            """,
            (
                document_id,
                depth,
                initial_status,
                discovered_from_edge_id,
            ),
        )

        self.connection.commit()

    def recover_interrupted_jobs(
        self,
    ) -> int:
        cursor = self.connection.execute(
            """
            UPDATE crawl_jobs
            SET
                status = 'pending',
                updated_at = CURRENT_TIMESTAMP
            WHERE status = 'fetching'
            """
        )

        self.connection.commit()

        return cursor.rowcount

    def claim_next(
        self,
        *,
        max_depth: int | None = None,
        organizations: (
            tuple[str, ...] | None
        ) = None,
    ) -> CrawlJob | None:
        where = (
            "job.status = 'pending'"
        )

        parameters: list[Any] = []

        if max_depth is not None:
            where += (
                " AND job.depth <= ?"
            )

            parameters.append(
                max_depth
            )

        if organizations:
            normalized_orgs = tuple(
                org.strip().upper()
                for org in organizations
                if org.strip()
            )

            if normalized_orgs:
                placeholders = ", ".join(
                    "?"
                    for _ in normalized_orgs
                )

                where += (
                    " AND document.org IN "
                    f"({placeholders})"
                )

                parameters.extend(
                    normalized_orgs
                )

        try:
            self.connection.execute(
                "BEGIN IMMEDIATE"
            )

            row = self.connection.execute(
                f"""
                SELECT
                    job.document_id,
                    document.org,
                    document.code,
                    document.title,
                    job.depth,
                    job.status,
                    job.attempts,
                    job.discovered_from_edge_id
                FROM crawl_jobs AS job

                JOIN documents AS document
                    ON document.id =
                       job.document_id

                WHERE {where}

                ORDER BY
                    job.depth,
                    job.document_id

                LIMIT 1
                """,
                parameters,
            ).fetchone()

            if row is None:
                self.connection.commit()
                return None

            self.connection.execute(
                """
                UPDATE crawl_jobs
                SET
                    status = 'fetching',
                    attempts = attempts + 1,
                    last_error = '',
                    updated_at =
                        CURRENT_TIMESTAMP
                WHERE document_id = ?
                """,
                (
                    row["document_id"],
                ),
            )

            self.connection.commit()

        except Exception:
            self.connection.rollback()
            raise

        return CrawlJob(
            document_id=(
                row["document_id"]
            ),
            org=row["org"],
            code=row["code"],
            title=row["title"],
            depth=row["depth"],
            status="fetching",
            attempts=(
                row["attempts"] + 1
            ),
            discovered_from_edge_id=(
                row[
                    "discovered_from_edge_id"
                ]
            ),
        )

    def mark_status(
        self,
        *,
        document_id: str,
        status: str,
        source_url: str = "",
        last_error: str = "",
    ) -> None:
        normalized_status = (
            status.strip().casefold()
        )

        if (
            normalized_status
            not in VALID_STATUSES
        ):
            raise ValueError(
                "Geçersiz crawl status: "
                f"{status}"
            )

        cursor = self.connection.execute(
            """
            UPDATE crawl_jobs
            SET
                status = ?,
                source_url = ?,
                last_error = ?,
                updated_at =
                    CURRENT_TIMESTAMP
            WHERE document_id = ?
            """,
            (
                normalized_status,
                source_url.strip(),
                last_error.strip(),
                document_id,
            ),
        )

        if cursor.rowcount != 1:
            self.connection.rollback()

            raise KeyError(
                "Crawl job bulunamadı: "
                f"{document_id}"
            )

        self.connection.commit()

    def mark_failure(
        self,
        *,
        document_id: str,
        error: str,
        max_attempts: int = 3,
    ) -> str:
        row = self.connection.execute(
            """
            SELECT attempts
            FROM crawl_jobs
            WHERE document_id = ?
            """,
            (document_id,),
        ).fetchone()

        if row is None:
            raise KeyError(
                "Crawl job bulunamadı: "
                f"{document_id}"
            )

        next_status = (
            "failed"
            if row["attempts"] >= max_attempts
            else "pending"
        )

        self.mark_status(
            document_id=document_id,
            status=next_status,
            last_error=error,
        )

        return next_status

    def status_counts(
        self,
    ) -> dict[str, int]:
        rows = self.connection.execute(
            """
            SELECT
                status,
                COUNT(*) AS total
            FROM crawl_jobs
            GROUP BY status
            ORDER BY status
            """
        ).fetchall()

        return {
            row["status"]: row["total"]
            for row in rows
        }