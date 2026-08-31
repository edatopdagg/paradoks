import tempfile
import unittest
from pathlib import Path

from v3_catalog import V3Catalog
from v3_crawl_queue import V3CrawlQueue


class V3CrawlQueueFilterTests(
    unittest.TestCase
):
    def test_claims_only_requested_organization(
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

            three_gpp_id = (
                catalog.upsert_document(
                    org="3GPP",
                    code="TS 22.003",
                    title="3GPP document",
                )
            )

            ietf_id = (
                catalog.upsert_document(
                    org="IETF",
                    code="2119",
                    title="IETF document",
                )
            )

            queue.enqueue_document(
                document_id=three_gpp_id,
                depth=1,
            )

            queue.enqueue_document(
                document_id=ietf_id,
                depth=1,
            )

            claimed = queue.claim_next(
                organizations=("IETF",),
            )

            self.assertIsNotNone(
                claimed
            )

            self.assertEqual(
                claimed.document_id,
                ietf_id,
            )

            self.assertEqual(
                claimed.org,
                "IETF",
            )

            catalog.close()


if __name__ == "__main__":
    unittest.main(verbosity=2)