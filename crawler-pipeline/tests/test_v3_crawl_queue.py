import tempfile
import unittest
from pathlib import Path

from v3_catalog import V3Catalog
from v3_crawl_queue import V3CrawlQueue


class V3CrawlQueueTests(
    unittest.TestCase
):
    def setUp(self):
        self.directory = (
            tempfile.TemporaryDirectory()
        )

        self.catalog = V3Catalog(
            Path(self.directory.name)
            / "catalog.sqlite3"
        )

        self.queue = V3CrawlQueue(
            self.catalog
        )

    def tearDown(self):
        self.catalog.close()
        self.directory.cleanup()

    def _document(
        self,
        org: str,
        code: str,
    ) -> str:
        return self.catalog.upsert_document(
            org=org,
            code=code,
            title=code,
        )

    def test_deduplicates_and_keeps_shallowest_depth(
        self,
    ):
        document_id = self._document(
            "3GPP",
            "TS 23.040",
        )

        self.queue.enqueue_document(
            document_id=document_id,
            depth=4,
        )

        self.queue.enqueue_document(
            document_id=document_id,
            depth=2,
        )

        row = self.catalog.connection.execute(
            """
            SELECT *
            FROM crawl_jobs
            WHERE document_id = ?
            """,
            (document_id,),
        ).fetchone()

        self.assertEqual(
            row["depth"],
            2,
        )

        self.assertEqual(
            row["status"],
            "pending",
        )

    def test_existing_document_version_is_already_indexed(
        self,
    ):
        document_id = self._document(
            "IETF",
            "4960",
        )

        self.catalog.upsert_version(
            document_id=document_id,
            version="RFC 4960",
            release="",
            source_url=(
                "https://example.test/"
                "rfc4960"
            ),
            local_path=(
                "documents/rfc4960.html"
            ),
        )

        self.queue.enqueue_document(
            document_id=document_id,
            depth=1,
        )

        self.assertEqual(
            self.queue.status_counts(),
            {"indexed": 1},
        )

        self.assertIsNone(
            self.queue.claim_next()
        )

    def test_claims_breadth_first_and_recovers_interruption(
        self,
    ):
        deep = self._document(
            "3GPP",
            "TS 29.002",
        )

        shallow = self._document(
            "3GPP",
            "TS 23.040",
        )

        self.queue.enqueue_document(
            document_id=deep,
            depth=2,
        )

        self.queue.enqueue_document(
            document_id=shallow,
            depth=1,
        )

        claimed = self.queue.claim_next()

        self.assertEqual(
            claimed.document_id,
            shallow,
        )

        self.assertEqual(
            claimed.attempts,
            1,
        )

        recovered = (
            self.queue
            .recover_interrupted_jobs()
        )

        self.assertEqual(
            recovered,
            1,
        )

        claimed_again = (
            self.queue.claim_next(
                max_depth=1
            )
        )

        self.assertEqual(
            claimed_again.document_id,
            shallow,
        )

        self.assertEqual(
            claimed_again.attempts,
            2,
        )

    def test_retries_then_marks_failed(
        self,
    ):
        document_id = self._document(
            "ETSI",
            "TS 102 182",
        )

        self.queue.enqueue_document(
            document_id=document_id,
            depth=1,
        )

        expected_statuses = (
            "pending",
            "pending",
            "failed",
        )

        for expected in expected_statuses:
            claimed = (
                self.queue.claim_next()
            )

            self.assertIsNotNone(
                claimed
            )

            status = (
                self.queue.mark_failure(
                    document_id=document_id,
                    error="temporary error",
                    max_attempts=3,
                )
            )

            self.assertEqual(
                status,
                expected,
            )

        self.assertIsNone(
            self.queue.claim_next()
        )

        self.assertEqual(
            self.queue.status_counts(),
            {"failed": 1},
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)