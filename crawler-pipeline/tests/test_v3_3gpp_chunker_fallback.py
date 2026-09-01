import sys
import unittest
from pathlib import Path
from unittest.mock import patch


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


from chunker import (
    split_into_clauses,
)


class ThreeGppChunkerFallbackTests(
    unittest.TestCase
):
    @patch(
        "chunker._split_3gpp_clauses",
        return_value=[],
    )
    def test_uses_clean_generic_fallback(
        self,
        split_mock,
    ):
        document_text = (
            "3GPP TS 34.108 "
            "V15.2.0 (2019-09)\n"
            "Content\n"
            "1 Scope 50\n"
            "2 References 50\n"
            "Front matter text.\n"
            "         1  Scope\n"
            "The present document defines "
            "reference conditions and common "
            "test environments for user "
            "equipment conformance testing.\n"
            "This scope text must remain "
            "searchable after fallback.\n"
            "2  References\n"
            "The following documents contain "
            "provisions used by this standard."
        )

        clauses = split_into_clauses(
            document_text=document_text,
            doc_org="3GPP",
        )

        self.assertTrue(
            split_mock.called
        )

        self.assertGreater(
            len(clauses),
            0,
        )

        self.assertEqual(
            clauses[0][0],
            "1",
        )

        self.assertEqual(
            clauses[0][1],
            "Scope",
        )

        self.assertIn(
            "reference conditions",
            clauses[0][2],
        )

        self.assertNotIn(
            "Scope 50",
            clauses[0][1],
        )


if __name__ == "__main__":
    unittest.main(
        verbosity=2
    )
