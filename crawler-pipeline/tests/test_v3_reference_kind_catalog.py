import sqlite3
import tempfile
import unittest
from pathlib import Path

from v3_catalog import V3Catalog


class ReferenceKindCatalogTests(unittest.TestCase):
    def test_stores_and_updates_reference_kind(self):
        with tempfile.TemporaryDirectory() as directory:
            catalog = V3Catalog(Path(directory) / "catalog.sqlite3")
            document_id = catalog.upsert_document(
                org="IETF",
                code="4960",
                title="Stream Control Transmission Protocol",
            )
            version_id = catalog.upsert_version(
                document_id=document_id,
                version="RFC 4960",
                release="",
                source_url="https://www.rfc-editor.org/rfc/rfc4960.html",
                local_path="documents/ietf/4960/rfc4960.html",
            )
            target_id = catalog.upsert_document(
                org="IETF",
                code="2119",
                title="Key words for use in RFCs",
            )

            edge_id = catalog.upsert_reference(
                source_version_id=version_id,
                source_clause_id=None,
                target_document_id=target_id,
                target_org="IETF",
                target_code="2119",
                ref_number=None,
                raw_text="[RFC2119]",
                reference_kind="normative",
            )
            edge = catalog.connection.execute(
                "SELECT * FROM reference_edges WHERE id = ?",
                (edge_id,),
            ).fetchone()

            self.assertEqual(edge["reference_kind"], "normative")
            catalog.close()

    def test_migrates_existing_catalog_without_losing_edges(self):
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "legacy.sqlite3"
            connection = sqlite3.connect(database_path)
            connection.execute(
                """
                CREATE TABLE reference_edges (
                    id TEXT PRIMARY KEY,
                    source_version_id TEXT NOT NULL,
                    source_clause_id TEXT,
                    target_document_id TEXT,
                    target_org TEXT NOT NULL,
                    target_code TEXT NOT NULL,
                    ref_number INTEGER,
                    raw_text TEXT NOT NULL DEFAULT ''
                )
                """
            )
            connection.execute(
                """
                INSERT INTO reference_edges(
                    id, source_version_id, target_org, target_code, raw_text
                ) VALUES ('edge_old', 'version_old', '3GPP', 'TS 23.040', '[4]')
                """
            )
            connection.commit()
            connection.close()

            catalog = V3Catalog(database_path)
            edge = catalog.connection.execute(
                "SELECT * FROM reference_edges WHERE id = 'edge_old'"
            ).fetchone()

            self.assertIsNotNone(edge)
            self.assertEqual(edge["reference_kind"], "unspecified")
            catalog.close()

    def test_rejects_unknown_reference_kind(self):
        with tempfile.TemporaryDirectory() as directory:
            catalog = V3Catalog(Path(directory) / "catalog.sqlite3")
            with self.assertRaises(ValueError):
                catalog.upsert_reference(
                    source_version_id="version",
                    source_clause_id=None,
                    target_document_id=None,
                    target_org="IETF",
                    target_code="2119",
                    ref_number=None,
                    raw_text="",
                    reference_kind="mandatory",
                )
            catalog.close()


if __name__ == "__main__":
    unittest.main(verbosity=2)
