import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from models import Chunk, DocStatus
from v3_catalog import V3Catalog
from v3_crawl_queue import V3CrawlQueue
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


    def test_uses_indexed_opposite_3gpp_type_as_canonical_reference(self):
        with tempfile.TemporaryDirectory() as directory:
            catalog = V3Catalog(
                Path(directory) / "catalog.sqlite3"
            )

            canonical_title = (
                "NR; User Equipment (UE) radio transmission "
                "and reception; Part 4: Performance requirements"
            )

            # Gerçek/canonical belge önceden doğrulanmış ve indekslenmiş.
            canonical_document_id = catalog.upsert_document(
                org="3GPP",
                code="TS 38.101-4",
                title=canonical_title,
            )

            catalog.upsert_version(
                document_id=canonical_document_id,
                version="19.3.0",
                release="19",
                source_url=(
                    "https://www.3gpp.org/ftp/Specs/archive/"
                    "38_series/38.101-4/38101-4-j30.zip"
                ),
                local_path=(
                    "documents/3gpp/ts-38-101-4/"
                    "19-3-0/38101-4-j30.docx"
                ),
                content_sha256="canonical-hash",
                is_latest=True,
            )

            # Kaynak standartta typo var:
            # Gerçekte TS olan belge TR diye yazılmış.
            source_document = V3DocumentInput(
                org="3GPP",
                code="TS 38.174",
                title=(
                    "NR Integrated access and backhaul "
                    "radio transmission and reception"
                ),
                version="19.2.0",
                release="19",
                source_url=(
                    "https://www.3gpp.org/ftp/Specs/archive/"
                    "38_series/38.174/38174-j20.zip"
                ),
                local_path=(
                    "documents/3gpp/ts-38-174/"
                    "19-2-0/38174-j20.docx"
                ),
                content_sha256="source-hash",
                document_text=(
                    '[28] 3GPP TR 38.101-4: '
                    '"NR; User Equipment (UE) radio transmission '
                    'and reception; Part 4: Performance requirements"'
                ),
            )

            fake_chunks = [
                _chunk(
                    "References\nUseful content",
                    "2",
                    "References",
                )
            ]

            with patch(
                "v3_ingestor.build_chunks",
                return_value=fake_chunks,
            ):
                result = ingest_document(
                    catalog=catalog,
                    document=source_document,
                )

            edge = catalog.connection.execute(
                """
                SELECT
                    target_document_id,
                    target_org,
                    target_code
                FROM reference_edges
                WHERE source_version_id = ?
                """,
                (result.version_id,),
            ).fetchone()

            self.assertIsNotNone(edge)

            # Beklenen canonical davranış:
            # kaynak TR yazsa bile doğrulanmış TS kimliğine bağlan.
            self.assertEqual(
                edge["target_document_id"],
                canonical_document_id,
            )

            self.assertEqual(
                edge["target_org"],
                "3GPP",
            )

            self.assertEqual(
                edge["target_code"],
                "TS 38.101-4",
            )

            # Sahte alias document hiç oluşmamalı.
            false_alias_count = catalog.connection.execute(
                """
                SELECT COUNT(*)
                FROM documents
                WHERE org = '3GPP'
                  AND code = 'TR 38.101-4'
                """
            ).fetchone()[0]

            self.assertEqual(
                false_alias_count,
                0,
            )

            catalog.close()



    def test_keeps_verified_3gpp_tr_reference_unchanged(self):
        with tempfile.TemporaryDirectory() as directory:
            catalog = V3Catalog(
                Path(directory) / "catalog.sqlite3"
            )

            canonical_title = (
                "Study on channel model for frequencies "
                "from 0.5 to 100 GHz"
            )

            # Gerçek TR belge önceden doğrulanmış.
            canonical_document_id = catalog.upsert_document(
                org="3GPP",
                code="TR 38.901",
                title=canonical_title,
            )

            catalog.upsert_version(
                document_id=canonical_document_id,
                version="19.0.0",
                release="19",
                source_url=(
                    "https://www.3gpp.org/ftp/Specs/archive/"
                    "38_series/38.901/38901-j00.zip"
                ),
                local_path=(
                    "documents/3gpp/tr-38-901/"
                    "19-0-0/38901-j00.docx"
                ),
                content_sha256="canonical-tr-hash",
                is_latest=True,
            )

            source_document = V3DocumentInput(
                org="3GPP",
                code="TS 38.174",
                title=(
                    "NR Integrated access and backhaul "
                    "radio transmission and reception"
                ),
                version="19.2.0",
                release="19",
                source_url=(
                    "https://www.3gpp.org/ftp/Specs/archive/"
                    "38_series/38.174/38174-j20.zip"
                ),
                local_path=(
                    "documents/3gpp/ts-38-174/"
                    "19-2-0/38174-j20.docx"
                ),
                content_sha256="source-hash",
                document_text=(
                    '[27] 3GPP TR 38.901: '
                    '"Study on channel model for frequencies '
                    'from 0.5 to 100 GHz"'
                ),
            )

            fake_chunks = [
                _chunk(
                    "References\nUseful content",
                    "2",
                    "References",
                )
            ]

            with patch(
                "v3_ingestor.build_chunks",
                return_value=fake_chunks,
            ):
                result = ingest_document(
                    catalog=catalog,
                    document=source_document,
                )

            edge = catalog.connection.execute(
                """
                SELECT
                    target_document_id,
                    target_org,
                    target_code
                FROM reference_edges
                WHERE source_version_id = ?
                """,
                (result.version_id,),
            ).fetchone()

            self.assertIsNotNone(edge)

            self.assertEqual(
                edge["target_document_id"],
                canonical_document_id,
            )

            self.assertEqual(
                edge["target_org"],
                "3GPP",
            )

            self.assertEqual(
                edge["target_code"],
                "TR 38.901",
            )

            false_ts_count = catalog.connection.execute(
                """
                SELECT COUNT(*)
                FROM documents
                WHERE org = '3GPP'
                  AND code = 'TS 38.901'
                """
            ).fetchone()[0]

            self.assertEqual(
                false_ts_count,
                0,
            )

            catalog.close()



    def test_repairs_opposite_3gpp_alias_when_canonical_is_indexed_later(self):
        with tempfile.TemporaryDirectory() as directory:
            catalog = V3Catalog(
                Path(directory) / "catalog.sqlite3"
            )
            queue = V3CrawlQueue(catalog)

            canonical_title = (
                "NR; User Equipment (UE) radio transmission "
                "and reception; Part 4: Performance requirements"
            )

            # 1) Önce hatalı kaynak gelir.
            # O anda canonical TS henüz doğrulanmış değildir.
            source_document = V3DocumentInput(
                org="3GPP",
                code="TS 38.174",
                title=(
                    "NR Integrated access and backhaul "
                    "radio transmission and reception"
                ),
                version="19.2.0",
                release="19",
                source_url=(
                    "https://www.3gpp.org/ftp/Specs/archive/"
                    "38_series/38.174/38174-j20.zip"
                ),
                local_path="documents/38174-j20.docx",
                content_sha256="source-hash",
                document_text=(
                    '[28] 3GPP TR 38.101-4: '
                    '"NR; User Equipment (UE) radio transmission '
                    'and reception; Part 4: Performance requirements"'
                ),
            )

            fake_source_chunks = [
                _chunk(
                    "References\nUseful content",
                    "2",
                    "References",
                )
            ]

            with patch(
                "v3_ingestor.build_chunks",
                return_value=fake_source_chunks,
            ):
                source_result = ingest_document(
                    catalog=catalog,
                    document=source_document,
                )

            bad_edge = catalog.connection.execute(
                """
                SELECT *
                FROM reference_edges
                WHERE source_version_id = ?
                """,
                (source_result.version_id,),
            ).fetchone()

            self.assertIsNotNone(bad_edge)
            self.assertEqual(
                bad_edge["target_code"],
                "TR 38.101-4",
            )

            alias_document_id = (
                bad_edge["target_document_id"]
            )

            # Gerçek crawler davranışını simüle et:
            # yanlış alias kuyruğa depth=3 olarak girmiş.
            queue.enqueue_document(
                document_id=alias_document_id,
                depth=3,
                discovered_from_edge_id=bad_edge["id"],
            )

            # 2) Daha sonra gerçek canonical TS belge gelir
            # ve başarıyla indekslenir.
            canonical_document = V3DocumentInput(
                org="3GPP",
                code="TS 38.101-4",
                title=canonical_title,
                version="19.3.0",
                release="19",
                source_url=(
                    "https://www.3gpp.org/ftp/Specs/archive/"
                    "38_series/38.101-4/38101-4-j30.zip"
                ),
                local_path="documents/38101-4-j30.docx",
                content_sha256="canonical-hash",
                document_text=(
                    "1 Scope\n"
                    "Canonical specification content."
                ),
            )

            fake_canonical_chunks = [
                _chunk(
                    "Scope\nCanonical specification content.",
                    "1",
                    "Scope",
                )
            ]

            with patch(
                "v3_ingestor.build_chunks",
                return_value=fake_canonical_chunks,
            ):
                canonical_result = ingest_document(
                    catalog=catalog,
                    document=canonical_document,
                )

            # 3) Artık eski TR alias tamamen canonical TS'ye
            # taşınmış olmalı.
            repaired_edge = catalog.connection.execute(
                """
                SELECT
                    id,
                    target_document_id,
                    target_code
                FROM reference_edges
                WHERE source_version_id = ?
                """,
                (source_result.version_id,),
            ).fetchone()

            self.assertIsNotNone(repaired_edge)

            self.assertEqual(
                repaired_edge["target_document_id"],
                canonical_result.document_id,
            )

            self.assertEqual(
                repaired_edge["target_code"],
                "TS 38.101-4",
            )

            alias_count = catalog.connection.execute(
                """
                SELECT COUNT(*)
                FROM documents
                WHERE id = ?
                """,
                (alias_document_id,),
            ).fetchone()[0]

            self.assertEqual(
                alias_count,
                0,
            )

            alias_job_count = catalog.connection.execute(
                """
                SELECT COUNT(*)
                FROM crawl_jobs
                WHERE document_id = ?
                """,
                (alias_document_id,),
            ).fetchone()[0]

            self.assertEqual(
                alias_job_count,
                0,
            )

            canonical_job = catalog.connection.execute(
                """
                SELECT
                    depth,
                    status
                FROM crawl_jobs
                WHERE document_id = ?
                """,
                (canonical_result.document_id,),
            ).fetchone()

            self.assertIsNotNone(
                canonical_job
            )

            # Alias'ın daha sığ keşif depth'i kaybolmamalı.
            self.assertEqual(
                canonical_job["depth"],
                3,
            )

            self.assertEqual(
                canonical_job["status"],
                "indexed",
            )

            catalog.close()



if __name__ == "__main__":
    unittest.main(verbosity=2)
