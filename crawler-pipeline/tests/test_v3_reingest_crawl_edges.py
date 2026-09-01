import sys
import tempfile
import unittest
from pathlib import Path


PIPELINE_ROOT = (
    Path(__file__)
    .resolve()
    .parents[1]
)

sys.path.insert(
    0,
    str(
        PIPELINE_ROOT
        / "src"
    ),
)

from v3_catalog import V3Catalog
from v3_crawl_queue import V3CrawlQueue
from v3_ingestor import (
    V3DocumentInput,
    ingest_document,
)


class ReingestCrawlEdgeTests(
    unittest.TestCase
):
    def test_preserves_job_when_old_edge_is_rebuilt(
        self,
    ):
        with tempfile.TemporaryDirectory() as directory:
            catalog = V3Catalog(
                Path(directory)
                / "catalog.sqlite3"
            )

            queue = V3CrawlQueue(
                catalog
            )

            source_document = V3DocumentInput(
                org="IETF",
                code="9113",
                title="HTTP/2",
                version="RFC 9113",
                release="",
                source_url=(
                    "https://www.rfc-editor.org/"
                    "rfc/rfc9113.html"
                ),
                local_path=(
                    "documents/ietf/9113/"
                    "rfc-9113/rfc9113.html"
                ),
                content_sha256="first",
                document_text=(
                    "1.\n"
                    "Introduction\n"
                    "HTTP/2 permits concurrent "
                    "streams.\n"
                    "\n"
                    "2.\n"
                    "Protocol Overview\n"
                    "HTTP/2 uses one connection."
                ),
            )

            first_result = ingest_document(
                catalog=catalog,
                document=source_document,
            )

            source_clause = (
                catalog.connection.execute(
                    """
                    SELECT id
                    FROM clauses
                    WHERE version_id = ?
                    ORDER BY number
                    LIMIT 1
                    """,
                    (
                        first_result.version_id,
                    ),
                ).fetchone()
            )

            target_document_id = (
                catalog.upsert_document(
                    org="IETF",
                    code="7540",
                    title="HTTP/2 Legacy",
                )
            )

            edge_id = "edge-test-reingest"

            catalog.connection.execute(
                """
                INSERT INTO reference_edges (
                    id,
                    source_version_id,
                    source_clause_id,
                    target_document_id,
                    target_org,
                    target_code,
                    ref_number,
                    raw_text,
                    reference_kind
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    edge_id,
                    first_result.version_id,
                    source_clause["id"],
                    target_document_id,
                    "IETF",
                    "7540",
                    1,
                    "RFC 7540",
                    "normative",
                ),
            )

            catalog.connection.commit()

            queue.enqueue_document(
                document_id=target_document_id,
                depth=1,
                discovered_from_edge_id=edge_id,
            )

            second_document = V3DocumentInput(
                org=source_document.org,
                code=source_document.code,
                title=source_document.title,
                version=source_document.version,
                release=source_document.release,
                source_url=source_document.source_url,
                local_path=source_document.local_path,
                content_sha256="second",
                document_text=(
                    source_document.document_text
                    + "\nAdditional protocol text."
                ),
            )

            second_result = ingest_document(
                catalog=catalog,
                document=second_document,
            )

            job = (
                catalog.connection.execute(
                    """
                    SELECT
                        document_id,
                        discovered_from_edge_id
                    FROM crawl_jobs
                    WHERE document_id = ?
                    """,
                    (
                        target_document_id,
                    ),
                ).fetchone()
            )

            old_edge = (
                catalog.connection.execute(
                    """
                    SELECT id
                    FROM reference_edges
                    WHERE id = ?
                    """,
                    (
                        edge_id,
                    ),
                ).fetchone()
            )

            self.assertGreater(
                second_result.chunk_count,
                0,
            )
            self.assertIsNotNone(
                job,
            )
            self.assertIsNone(
                job["discovered_from_edge_id"]
            )
            self.assertIsNone(
                old_edge
            )

            catalog.close()


if __name__ == "__main__":
    unittest.main(
        verbosity=2
    )
