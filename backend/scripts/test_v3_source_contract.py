import ast
import re
import sys
import unittest
from pathlib import Path
from typing import Any


BACKEND_ROOT = (
    Path(__file__)
    .resolve()
    .parents[1]
)

sys.path.insert(
    0,
    str(BACKEND_ROOT),
)

from app.schemas import Source


def load_build_sources():
    service_path = (
        BACKEND_ROOT
        / "app"
        / "services"
        / "chat_service.py"
    )

    syntax_tree = ast.parse(
        service_path.read_text(
            encoding="utf-8",
        )
    )

    function_node = next(
        node
        for node in syntax_tree.body
        if isinstance(
            node,
            ast.FunctionDef,
        )
        and node.name == "_build_sources"
    )

    isolated_module = ast.Module(
        body=[function_node],
        type_ignores=[],
    )

    ast.fix_missing_locations(
        isolated_module
    )

    namespace = {
        "Any": Any,
        "re": re,
    }

    exec(
        compile(
            isolated_module,
            str(service_path),
            "exec",
        ),
        namespace,
    )

    return namespace[
        "_build_sources"
    ]


class V3SourceContractTests(
    unittest.TestCase
):
    def test_maps_exact_v3_source_location(
        self,
    ):
        build_sources = (
            load_build_sources()
        )

        mapped = build_sources(
            [
                {
                    "id": "chunk-1",
                    "text": (
                        "Warning message "
                        "cancel procedure."
                    ),
                    "distance": 0.12,
                    "metadata": {
                        "source_id": "chunk-1",
                        "document_id": "doc-1",
                        "version_id": "version-1",
                        "clause_id": "clause-1",
                        "org": "3GPP",
                        "code": "TS 23.041",
                        "version": "20.0.0",
                        "clause": "9.1.3.4.3",
                        "clause_title": (
                            "Warning Message "
                            "Cancel Procedure"
                        ),
                        "page_start": 11,
                        "page_end": 12,
                        "source_url": (
                            "https://example.test/"
                            "23041-k00.zip"
                        ),
                        "local_path": (
                            "documents/3gpp/"
                            "ts-23-041/20.0.0/"
                            "23041-k00.docx"
                        ),
                        "viewer_url": (
                            "/sources/version-1/"
                            "clauses/clause-1"
                        ),
                        "char_start": 100,
                        "char_end": 180,
                        "status": "indexed",
                    },
                }
            ]
        )

        self.assertEqual(
            len(mapped),
            1,
        )

        source = Source(
            **mapped[0]
        )

        self.assertEqual(
            source.source_id,
            "chunk-1",
        )
        self.assertEqual(
            source.version_id,
            "version-1",
        )
        self.assertEqual(
            source.clause_id,
            "clause-1",
        )
        self.assertEqual(
            source.page_number,
            11,
        )
        self.assertEqual(
            source.page_start,
            11,
        )
        self.assertEqual(
            source.page_end,
            12,
        )
        self.assertEqual(
            source.char_start,
            100,
        )
        self.assertEqual(
            source.char_end,
            180,
        )
        self.assertIn(
            "clause-1",
            source.viewer_url,
        )
        self.assertIn(
            "cancel procedure",
            source.highlight_text,
        )

    def test_converts_missing_pages_to_none(
        self,
    ):
        build_sources = (
            load_build_sources()
        )

        mapped = build_sources(
            [
                {
                    "id": "chunk-2",
                    "text": "Scope text",
                    "distance": 0.2,
                    "metadata": {
                        "org": "IETF",
                        "code": "9113",
                        "version": "RFC 9113",
                        "clause": "1",
                        "clause_title": "Introduction",
                        "page_start": -1,
                        "page_end": -1,
                        "source_url": (
                            "https://example.test/"
                            "rfc9113.html"
                        ),
                        "status": "indexed",
                    },
                }
            ]
        )

        source = Source(
            **mapped[0]
        )

        self.assertIsNone(
            source.page_number
        )
        self.assertIsNone(
            source.page_start
        )
        self.assertIsNone(
            source.page_end
        )


if __name__ == "__main__":
    unittest.main(
        verbosity=2
    )
