import tempfile
import unittest
from pathlib import Path

from v3_catalog import V3Catalog


class V3DataModelTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_directory = (
            tempfile.TemporaryDirectory()
        )

        catalog_path = (
            Path(self.temp_directory.name)
            / "catalog.sqlite3"
        )

        self.catalog = V3Catalog(
            catalog_path
        )

    def tearDown(self) -> None:
        self.catalog.close()
        self.temp_directory.cleanup()

    def test_stores_exact_source_location(self) -> None:
        document_id = (
            self.catalog.upsert_document(
                org="3GPP",
                code="TS 23.041",
                title=(
                    "Technical realisation "
                    "of Cell Broadcast Service"
                ),
            )
        )

        version_id = (
            self.catalog.upsert_version(
                document_id=document_id,
                version="20.0.0",
                release="20",
                source_url=(
                    "https://example.test/"
                    "23041-k00.zip"
                ),
                local_path=(
                    "documents/3gpp/"
                    "ts-23-041/20.0.0/"
                    "23041-k00.docx"
                ),
            )
        )

        clause_id = (
            self.catalog.upsert_clause(
                version_id=version_id,
                number="9.1.2.1",
                title="Example procedure",
                body_text=(
                    "The network initiates "
                    "the example procedure."
                ),
                page_start=None,
                page_end=None,
            )
        )

        chunk_text = (
            "The network initiates "
            "the example procedure."
        )

        chunk_id = (
            self.catalog.upsert_chunk(
                clause_id=clause_id,
                text=chunk_text,
                chunk_index=0,
                char_start=0,
                char_end=len(chunk_text),
            )
        )

        locator = (
            self.catalog.get_source_locator(
                chunk_id
            )
        )

        self.assertIsNotNone(locator)
        self.assertEqual(
            locator["org"],
            "3GPP",
        )
        self.assertEqual(
            locator["code"],
            "TS 23.041",
        )
        self.assertEqual(
            locator["version"],
            "20.0.0",
        )
        self.assertEqual(
            locator["clause"],
            "9.1.2.1",
        )
        self.assertEqual(
            locator["clause_title"],
            "Example procedure",
        )
        self.assertEqual(
            locator["highlight_text"],
            chunk_text,
        )
        self.assertEqual(
            locator["viewer_url"],
            (
                f"/sources/{version_id}"
                f"/clauses/{clause_id}"
            ),
        )

    def test_preserves_reference_edges(self) -> None:
        source_document_id = (
            self.catalog.upsert_document(
                org="3GPP",
                code="TS 23.041",
                title="Cell Broadcast Service",
            )
        )

        source_version_id = (
            self.catalog.upsert_version(
                document_id=source_document_id,
                version="20.0.0",
                release="20",
                source_url="https://example.test/source",
                local_path="documents/source.docx",
            )
        )

        target_document_id = (
            self.catalog.upsert_document(
                org="3GPP",
                code="TS 23.040",
                title=(
                    "Technical realisation "
                    "of SMS"
                ),
            )
        )

        edge_id = (
            self.catalog.upsert_reference(
                source_version_id=(
                    source_version_id
                ),
                source_clause_id=None,
                target_document_id=(
                    target_document_id
                ),
                target_org="3GPP",
                target_code="TS 23.040",
                ref_number=1,
                raw_text=(
                    "[1] 3GPP TS 23.040: "
                    "Technical realisation of SMS"
                ),
            )
        )

        edges = (
            self.catalog.list_references(
                source_version_id
            )
        )

        self.assertTrue(edge_id)
        self.assertEqual(
            len(edges),
            1,
        )
        self.assertEqual(
            edges[0]["target_code"],
            "TS 23.040",
        )
        self.assertEqual(
            edges[0]["ref_number"],
            1,
        )

    def test_upserts_are_deterministic(self) -> None:
        first_id = (
            self.catalog.upsert_document(
                org="3GPP",
                code="TS 23.041",
                title="First title",
            )
        )

        second_id = (
            self.catalog.upsert_document(
                org="3gpp",
                code="ts 23.041",
                title="Updated title",
            )
        )

        self.assertEqual(
            first_id,
            second_id,
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)