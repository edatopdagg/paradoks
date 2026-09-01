import sys
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

from v3_ingestor import V3IngestResult
from v3_recursive_worker import (
    _require_indexable_result,
)


class RecursiveWorkerGuardTests(
    unittest.TestCase
):
    def test_accepts_document_with_chunks(
        self,
    ):
        result = V3IngestResult(
            document_id="doc-1",
            version_id="version-1",
            clause_count=2,
            chunk_count=4,
            reference_count=1,
        )

        _require_indexable_result(
            result
        )

    def test_rejects_zero_chunk_document(
        self,
    ):
        result = V3IngestResult(
            document_id="doc-2",
            version_id="version-2",
            clause_count=0,
            chunk_count=0,
            reference_count=0,
        )

        with self.assertRaisesRegex(
            ValueError,
            "chunk",
        ):
            _require_indexable_result(
                result
            )


if __name__ == "__main__":
    unittest.main(
        verbosity=2
    )
