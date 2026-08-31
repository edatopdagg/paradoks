import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from models import Chunk, DocStatus
from v3_catalog import V3Catalog
from v3_ingestor import V3DocumentInput, ingest_document


def _chunk(text: str, clause: str, title: str) -> Chunk:
    return Chunk(
        text=text,
        doc_org="IETF",
        doc_code="4960",
        version="RFC 4960",
        clause=clause,
        clause_title=title,
        status=DocStatus.INDEXED,
        source_url="https://www.rfc-editor.org/rfc/rfc4960.html",
    )


class V3IngestorTests(unittest.TestCase):
    def test_ingests_chunks_pages_and_typed_reference_edges(self):
        with tempfile.TemporaryDirectory() as directory:
            catalog = V3Catalog(Path(directory) / "catalog.sqlite3")
            document = V3DocumentInput(
                org="IETF",
                code="4960",
                title="Stream Control Transmission Protocol",
                version="RFC 4960",
                release="",
                source_url="https://www.rfc-editor.org/rfc/rfc4960.html",
                local_path="documents/ietf/4960/rfc4960.html",
                content_sha256="abc",
                document_text=(
                    "Normative References\n"
                    "[\nRFC2119\n] Bradner, S., \"Key words for use in RFCs\".\n"
                    "Informative References\n"
                    "[\nRFC4086\n] Eastlake, D., \"Randomness Requirements\"."
                ),
                page_texts=(
                    "First page",
                    "The association procedure carries a sufficiently long exact sentence.",
                ),
            )
            fake_chunks = [
                _chunk(
                    "Association Setup\nThe association procedure carries a sufficiently long exact sentence.",
                    "5.1",
                    "Association Setup",
                )
            ]

            with patch("v3_ingestor.build_chunks", return_value=fake_chunks):
                result = ingest_document(catalog=catalog, document=document)

            clause = catalog.connection.execute(
                "SELECT * FROM clauses WHERE version_id = ?",
                (result.version_id,),
            ).fetchone()
            edges = catalog.list_references(result.version_id)

            self.assertEqual(result.clause_count, 1)
            self.assertEqual(result.chunk_count, 1)
            self.assertEqual(result.reference_count, 2)
            self.assertEqual((clause["page_start"], clause["page_end"]), (2, 2))
            self.assertEqual(
                {edge["reference_kind"] for edge in edges},
                {"normative", "informative"},
            )
            catalog.close()

    def test_reingest_is_deterministic(self):
        with tempfile.TemporaryDirectory() as directory:
            catalog = V3Catalog(Path(directory) / "catalog.sqlite3")
            document = V3DocumentInput(
                org="3GPP",
                code="TS 23.040",
                title="SMS",
                version="19.0.0",
                release="19",
                source_url="https://example.test/23040-j00.zip",
                local_path="documents/23040-j00.docx",
                content_sha256="abc",
                document_text='[1] 3GPP TS 23.041: "CBS"',
            )
            fake_chunks = [_chunk("Scope\nUseful content", "1", "Scope")]

            with patch("v3_ingestor.build_chunks", return_value=fake_chunks):
                first = ingest_document(catalog=catalog, document=document)
                second = ingest_document(catalog=catalog, document=document)

            counts = {
                table: catalog.connection.execute(
                    f"SELECT COUNT(*) FROM {table}"
                ).fetchone()[0]
                for table in ("document_versions", "clauses", "chunks", "reference_edges")
            }
            self.assertEqual(first, second)
            self.assertEqual(counts["document_versions"], 1)
            self.assertEqual(counts["clauses"], 1)
            self.assertEqual(counts["chunks"], 1)
            self.assertEqual(counts["reference_edges"], 1)
            catalog.close()


if __name__ == "__main__":
    unittest.main(verbosity=2)
