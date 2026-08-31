import unittest
from unittest.mock import patch

from models import (
    DocStatus,
    Reference,
)
from resolver import _resolve_3gpp


def make_reference(
    code: str,
) -> Reference:
    return Reference(
        raw_text=code,
        org="3GPP",
        code=code,
        title="Test document",
    )


class ThreeGppResolverTests(
    unittest.TestCase
):
    @patch(
        "resolver._links"
    )
    @patch(
        "resolver._get"
    )
    def test_ignores_underscore_archive(
        self,
        get_mock,
        links_mock,
    ):
        get_mock.return_value = object()

        links_mock.return_value = [
            "25925-h00.zip",
            "25925-j00.zip",
            "25925_310.zip",
        ]

        resolved = _resolve_3gpp(
            make_reference("TR 25.925")
        )

        self.assertEqual(
            resolved.status,
            DocStatus.PENDING,
        )

        self.assertTrue(
            resolved.source_url.endswith(
                "/25925-j00.zip"
            )
        )

        self.assertEqual(
            resolved.version,
            "25925-j00.zip",
        )

    @patch(
        "resolver._links"
    )
    @patch(
        "resolver._get"
    )
    def test_ignores_intermediate_archive(
        self,
        get_mock,
        links_mock,
    ):
        get_mock.return_value = object()

        links_mock.return_value = [
            "25331-j20.zip",
            "25331-j30.zip",
            "25331vIntermediate.zip",
        ]

        resolved = _resolve_3gpp(
            make_reference("TS 25.331")
        )

        self.assertTrue(
            resolved.source_url.endswith(
                "/25331-j30.zip"
            )
        )

        self.assertEqual(
            resolved.version,
            "25331-j30.zip",
        )

    @patch(
        "resolver._links"
    )
    @patch(
        "resolver._get"
    )
    def test_selects_latest_valid_version(
        self,
        get_mock,
        links_mock,
    ):
        get_mock.return_value = object()

        links_mock.return_value = [
            "../",
            "23041-j00.zip",
            (
                "/ftp/Specs/archive/"
                "23_series/23.041/"
                "23041-k00.zip"
            ),
            "99999-z99.zip",
            "23041_notes.zip",
        ]

        resolved = _resolve_3gpp(
            make_reference("TS 23.041")
        )

        self.assertTrue(
            resolved.source_url.endswith(
                "/23041-k00.zip"
            )
        )

    @patch(
        "resolver._links"
    )
    @patch(
        "resolver._get"
    )
    def test_returns_folder_when_no_valid_version(
        self,
        get_mock,
        links_mock,
    ):
        get_mock.return_value = object()

        links_mock.return_value = [
            "25925_310.zip",
            "25925vIntermediate.zip",
            "readme.zip",
        ]

        resolved = _resolve_3gpp(
            make_reference("TR 25.925")
        )

        self.assertEqual(
            resolved.status,
            DocStatus.PENDING,
        )

        self.assertTrue(
            resolved.source_url.endswith(
                "/25.925/"
            )
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
