import unittest

from v3_ingestor import (
    _pages_for_text,
    _prepare_document_text,
)


class EtsiIngestionRegressionTests(
    unittest.TestCase
):
    def test_removes_front_matter_and_fake_date_clause(
        self,
    ):
        document_text = """
[[PAGE:3]]
Contents
1 Scope ........................................ 5

[[PAGE:5]]
5 ETSI TS 102 900 V1.4.1 (2023-06)
1 Scope
The actual scope content is here.
6.2 Special needs
Doc FCC 18-4: Second Report and Order,
31 January 2018.
ETSI
"""

        cleaned = _prepare_document_text(
            "ETSI",
            document_text,
        )

        self.assertTrue(
            cleaned.startswith("1 Scope")
        )

        self.assertNotIn(
            "Contents",
            cleaned,
        )

        self.assertNotIn(
            "5 ETSI TS 102 900",
            cleaned,
        )

        self.assertIn(
            " 31 January 2018.",
            cleaned,
        )

    def test_prefers_body_page_over_toc_page(
        self,
    ):
        pages = _pages_for_text(
            (
                "EU-Alert capabilities and "
                "requirements"
            ),
            (
                (
                    "Contents EU-Alert "
                    "capabilities and requirements"
                ),
                "Unrelated page",
                (
                    "EU-Alert capabilities "
                    "and requirements"
                ),
            ),
        )

        self.assertEqual(
            pages,
            [3],
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)