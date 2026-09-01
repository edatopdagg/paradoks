import unittest
from unittest.mock import patch

from models import (
    DocStatus,
    Reference,
)
from resolver import (
    _resolve_atis,
    _resolve_gsma,
    _resolve_itu,
)


def make_reference(
    org: str,
    code: str,
) -> Reference:
    return Reference(
        raw_text=code,
        org=org,
        code=code,
        title="Test document",
    )


class ItuResolverTests(
    unittest.TestCase
):
    @patch(
        "resolver._links"
    )
    @patch(
        "resolver._get"
    )
    def test_selects_free_english_pdf_link(
        self,
        get_mock,
        links_mock,
    ):
        landing_response = object()
        version_response = object()

        get_mock.side_effect = [
            landing_response,
            version_response,
        ]

        links_mock.side_effect = [
            [
                (
                    "./recommendation.asp?"
                    "lang=en&parent="
                    "T-REC-X.210-198811-S"
                ),
                (
                    "./recommendation.asp?"
                    "lang=en&parent="
                    "T-REC-X.210-199311-I"
                ),
            ],
            [
                (
                    "dologin_pub.asp?id="
                    "T-REC-X.210-199311-I"
                    "!!PDF-S&type=items"
                ),
                (
                    "dologin_pub.asp?id="
                    "T-REC-X.210-199311-I"
                    "!!PDF-E&type=items"
                ),
            ],
        ]

        resolved = _resolve_itu(
            make_reference(
                "ITU-T",
                "X.210",
            )
        )

        self.assertEqual(
            resolved.status,
            DocStatus.PENDING,
        )

        self.assertIn(
            "PDF-E",
            resolved.source_url,
        )

        self.assertIn(
            "199311-I",
            resolved.source_url,
        )

        second_request_url = (
            get_mock.call_args_list[1]
            .args[0]
        )

        self.assertIn(
            "T-REC-X.210-199311-I",
            second_request_url,
        )


    @patch(
        "resolver._links",
        return_value=[],
    )
    @patch(
        "resolver._get",
        return_value=object(),
    )
    def test_keeps_official_landing_page_when_blocked(
        self,
        get_mock,
        links_mock,
    ):
        resolved = _resolve_itu(
            make_reference(
                "ITU-T",
                "X.210",
            )
        )

        self.assertEqual(
            resolved.status,
            DocStatus.BLOCKED,
        )

        self.assertEqual(
            resolved.source_url,
            (
                "https://www.itu.int/rec/"
                "T-REC-X.210/en"
            ),
        )


class ExternalResolverFallbackTests(
    unittest.TestCase
):
    @patch(
        "resolver._search_google_pdf",
        return_value=None,
    )
    def test_atis_keeps_official_search_url(
        self,
        search_mock,
    ):
        resolved = _resolve_atis(
            make_reference(
                "ATIS",
                "0700041",
            )
        )

        self.assertEqual(
            resolved.status,
            DocStatus.BLOCKED,
        )

        self.assertEqual(
            resolved.source_url,
            "https://atis.org/?s=0700041",
        )

    @patch(
        "resolver._search_google_pdf",
        return_value=None,
    )
    def test_gsma_keeps_official_search_url(
        self,
        search_mock,
    ):
        resolved = _resolve_gsma(
            make_reference(
                "GSMA",
                "AD.26",
            )
        )

        self.assertEqual(
            resolved.status,
            DocStatus.BLOCKED,
        )

        self.assertEqual(
            resolved.source_url,
            "https://www.gsma.com/?s=AD.26",
        )

    @patch(
        "resolver._search_google_pdf",
        return_value=(
            "https://atis.org/document.pdf"
        ),
    )
    def test_atis_uses_pdf_when_available(
        self,
        search_mock,
    ):
        resolved = _resolve_atis(
            make_reference(
                "ATIS",
                "0700041",
            )
        )

        self.assertEqual(
            resolved.status,
            DocStatus.PENDING,
        )

        self.assertEqual(
            resolved.source_url,
            "https://atis.org/document.pdf",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
