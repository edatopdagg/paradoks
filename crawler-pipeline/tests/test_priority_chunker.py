import unittest

from priority_chunker import (
    _remove_postal_address_lines,
    _remove_toc_rows,
    _strip_single_character_runs,
    prepare_priority_text,
    build_priority_chunks,
)


class PriorityChunkQualityTests(
    unittest.TestCase
):

    def test_removes_garbled_character_run(
        self,
    ):

        text = (
            "Useful text\n"
            + "\n".join(
                list(
                    "ABCDEFGHIJKLMN"
                )
            )
            + "\nMore useful text"
        )

        cleaned = (
            _strip_single_character_runs(
                text
            )
        )

        self.assertIn(
            "Useful text",
            cleaned,
        )

        self.assertNotIn(
            "\nA\nB\nC\nD\n",
            cleaned,
        )


    def test_removes_cid_tokens(
        self,
    ):

        text = (
            "Useful technical text "
            "(cid:123) continues here "
            "(cid:45) without corruption."
        )

        cleaned = (
            prepare_priority_text(
                org="ATIS",
                document_text=text,
            )
        )

        self.assertNotIn(
            "(cid:",
            cleaned,
        )

        self.assertIn(
            "Useful technical text",
            cleaned,
        )

        self.assertIn(
            "continues here",
            cleaned,
        )


    def test_removes_toc_rows(
        self,
    ):

        text = (
            "1 Scope .............. 5\n"
            "Real technical text."
        )

        cleaned = (
            _remove_toc_rows(
                text
            )
        )

        self.assertNotIn(
            "........",
            cleaned,
        )


    def test_removes_postal_address(
        self,
    ):

        text = (
            "1200 G Street, NW\n"
            "1919 S. Eads St.\n"
            "Technical content here."
        )

        cleaned = (
            _remove_postal_address_lines(
                text
            )
        )

        self.assertNotIn(
            "1200 G Street",
            cleaned,
        )

        self.assertNotIn(
            "1919 S. Eads",
            cleaned,
        )

        self.assertIn(
            "Technical content",
            cleaned,
        )


    def test_atis_front_matter_removed(
        self,
    ):

        text = """
1200 G Street, NW
Washington DC

1 Scope ............... 5

1 Scope
Actual ATIS technical content.

2 References
Reference material.
"""

        cleaned = (
            prepare_priority_text(
                org="ATIS",
                document_text=text,
            )
        )

        self.assertNotIn(
            "1200 G Street",
            cleaned,
        )

        self.assertIn(
            "Actual ATIS technical content",
            cleaned,
        )


    def test_unstructured_vendor_gets_fallback(
        self,
    ):

        document_text = (
            "Unstructured vendor material. "
            * 4000
        )

        pages = (
            "Architecture and hardware information. "
            * 100,
            "Cell broadcast configuration information. "
            * 100,
        )

        result = (
            build_priority_chunks(
                document_text=document_text,
                page_texts=pages,
                doc_org="NOKIA",
                doc_code="TEST",
                version="",
                source_url=(
                    "priority://test.pdf"
                ),
            )
        )

        self.assertEqual(
            result["strategy"],
            "page_fallback",
        )

        self.assertGreater(
            len(
                result["chunks"]
            ),
            0,
        )


if __name__ == "__main__":

    unittest.main(
        verbosity=2
    )
