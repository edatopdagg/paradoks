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

from chunker import split_into_clauses
from v3_ingestor import (
    _prepare_document_text,
)


class IetfChunkerFallbackTests(
    unittest.TestCase
):
    def test_uses_generic_parser_when_ietf_parser_is_empty(
        self,
    ):
        modern_rfc_text = (
            "RFC 9113\n"
            "HTTP/2\n"
            "\n"
            "1.\n"
            "Introduction\n"
            "HTTP/2 permits concurrent "
            "streams.\n"
            "\n"
            "2.\n"
            "Protocol Overview\n"
            "HTTP/2 uses one connection."
        )

        prepared = (
            _prepare_document_text(
                "IETF",
                modern_rfc_text,
            )
        )

        with patch(
            "chunker._split_ietf_clauses",
            return_value=[],
        ):
            clauses = split_into_clauses(
                prepared,
                "IETF",
            )

        clause_pairs = {
            (
                number,
                title,
            )
            for (
                number,
                title,
                _,
            ) in clauses
        }

        self.assertIn(
            (
                "1",
                "Introduction",
            ),
            clause_pairs,
        )

        self.assertIn(
            (
                "2",
                "Protocol Overview",
            ),
            clause_pairs,
        )


if __name__ == "__main__":
    unittest.main(
        verbosity=2
    )
