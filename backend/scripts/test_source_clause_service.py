import sqlite3
import tempfile
import unittest
from pathlib import Path

from app.main import app
from app.services.source_service import (
    get_source_clause,
)


class SourceClauseServiceTests(
    unittest.TestCase
):
    def create_catalog(
        self,
        path: Path,
    ) -> None:
        connection = sqlite3.connect(
            str(path)
        )

        connection.executescript(
            """
            CREATE TABLE documents (
                id TEXT PRIMARY KEY,
                org TEXT NOT NULL,
                code TEXT NOT NULL,
                title TEXT NOT NULL
            );

            CREATE TABLE document_versions (
                id TEXT PRIMARY KEY,
                document_id TEXT NOT NULL,
                version TEXT NOT NULL,
                release TEXT NOT NULL,
                source_url TEXT NOT NULL,
                local_path TEXT NOT NULL
            );

            CREATE TABLE clauses (
                id TEXT PRIMARY KEY,
                version_id TEXT NOT NULL,
                number TEXT NOT NULL,
                title TEXT NOT NULL,
                body_text TEXT NOT NULL,
                page_start INTEGER,
                page_end INTEGER
            );
            """
        )

        connection.execute(
            """
            INSERT INTO documents (
                id,
                org,
                code,
                title
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                "doc-rfc9113",
                "IETF",
                "9113",
                "HTTP/2",
            ),
        )

        connection.execute(
            """
            INSERT INTO document_versions (
                id,
                document_id,
                version,
                release,
                source_url,
                local_path
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                "ver-rfc9113",
                "doc-rfc9113",
                "RFC 9113",
                "",
                (
                    "https://www.rfc-editor.org/"
                    "rfc/rfc9113.html"
                ),
                (
                    "documents/ietf/9113/"
                    "rfc-9113/rfc9113.html"
                ),
            ),
        )

        connection.execute(
            """
            INSERT INTO clauses (
                id,
                version_id,
                number,
                title,
                body_text,
                page_start,
                page_end
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "clause-streams",
                "ver-rfc9113",
                "5",
                "Streams and Multiplexing",
                (
                    "A single HTTP/2 connection "
                    "can contain multiple "
                    "concurrently open streams."
                ),
                None,
                None,
            ),
        )

        connection.commit()
        connection.close()

    def test_reads_exact_clause(
        self,
    ):
        with tempfile.TemporaryDirectory() as directory:
            catalog_path = (
                Path(directory)
                / "catalog.sqlite3"
            )

            self.create_catalog(
                catalog_path
            )

            result = get_source_clause(
                version_id="ver-rfc9113",
                clause_id="clause-streams",
                catalog_path=catalog_path,
            )

            self.assertEqual(
                result["org"],
                "IETF",
            )

            self.assertEqual(
                result["code"],
                "9113",
            )

            self.assertEqual(
                result["clause"],
                "5",
            )

            self.assertEqual(
                result["clause_title"],
                "Streams and Multiplexing",
            )

            self.assertIn(
                "multiple concurrently",
                result["body_text"],
            )

    def test_rejects_clause_from_another_version(
        self,
    ):
        with tempfile.TemporaryDirectory() as directory:
            catalog_path = (
                Path(directory)
                / "catalog.sqlite3"
            )

            self.create_catalog(
                catalog_path
            )

            with self.assertRaises(
                KeyError
            ):
                get_source_clause(
                    version_id="wrong-version",
                    clause_id="clause-streams",
                    catalog_path=catalog_path,
                )

    def test_reports_missing_catalog(
        self,
    ):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(
                FileNotFoundError
            ):
                get_source_clause(
                    version_id="version",
                    clause_id="clause",
                    catalog_path=(
                        Path(directory)
                        / "missing.sqlite3"
                    ),
                )

    def test_route_is_registered(
        self,
    ):
        paths = {
            route.path
            for route in app.routes
        }

        self.assertIn(
            (
                "/sources/{version_id}/"
                "clauses/{clause_id}"
            ),
            paths,
        )


if __name__ == "__main__":
    unittest.main(
        verbosity=2
    )
