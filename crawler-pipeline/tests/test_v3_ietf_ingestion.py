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
from v3_ingestor import (
    V3DocumentInput,
    ingest_document,
)


class ModernIetfIngestionTests(
    unittest.TestCase
):
    def test_ingests_split_rfc_headings(
        self,
    ):
        document_text = """
RFC 9113
HTTP/2
June 2022

1.
Introduction
HTTP/2 permits multiple concurrent
exchanges on the same connection.

1.1.
Purpose
This section describes the purpose
of the protocol.

2.
HTTP/2 Protocol Overview
HTTP/2 provides an optimized
expression of HTTP semantics.
""".strip()

        with tempfile.TemporaryDirectory() as directory:
            catalog = V3Catalog(
                Path(directory)
                / "catalog.sqlite3"
            )

            result = ingest_document(
                catalog=catalog,
                document=V3DocumentInput(
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
                    content_sha256=(
                        "test-modern-rfc"
                    ),
                    document_text=document_text,
                ),
            )

            clauses = (
                catalog.connection.execute(
                    """
                    SELECT number, title
                    FROM clauses
                    WHERE version_id = ?
                    ORDER BY number
                    """,
                    (
                        result.version_id,
                    ),
                ).fetchall()
            )

            clause_pairs = {
                (
                    row["number"],
                    row["title"],
                )
                for row in clauses
            }

            self.assertGreater(
                result.chunk_count,
                0,
            )

            self.assertIn(
                (
                    "1",
                    "Introduction",
                ),
                clause_pairs,
            )

            self.assertIn(
                (
                    "1.1",
                    "Purpose",
                ),
                clause_pairs,
            )

            self.assertIn(
                (
                    "2",
                    (
                        "HTTP/2 Protocol "
                        "Overview"
                    ),
                ),
                clause_pairs,
            )

            catalog.close()


if __name__ == "__main__":
    unittest.main(
        verbosity=2
    )
