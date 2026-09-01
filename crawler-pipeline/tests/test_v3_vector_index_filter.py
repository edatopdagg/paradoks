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
    str(PIPELINE_ROOT),
)

from build_v3_vector_index import (
    filter_rows,
)


class VectorIndexFilterTests(
    unittest.TestCase
):
    def setUp(
        self,
    ):
        self.rows = [
            {
                "org": "IETF",
                "code": "9113",
                "text": "HTTP/2",
            },
            {
                "org": "IETF",
                "code": "4960",
                "text": "SCTP",
            },
            {
                "org": "3GPP",
                "code": "TS 23.501",
                "text": "5GS",
            },
        ]

    def test_filters_by_org_and_code(
        self,
    ):
        filtered = filter_rows(
            self.rows,
            org="ietf",
            code=" 9113 ",
        )

        self.assertEqual(
            len(filtered),
            1,
        )
        self.assertEqual(
            filtered[0]["code"],
            "9113",
        )

    def test_filters_only_by_org(
        self,
    ):
        filtered = filter_rows(
            self.rows,
            org="IETF",
        )

        self.assertEqual(
            len(filtered),
            2,
        )

    def test_keeps_all_without_filters(
        self,
    ):
        filtered = filter_rows(
            self.rows
        )

        self.assertEqual(
            filtered,
            self.rows,
        )


if __name__ == "__main__":
    unittest.main(
        verbosity=2
    )
