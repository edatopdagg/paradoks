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


from models import Reference
from resolver import _resolve_3gpp


class ThreeGppResolverVersionTests(
    unittest.TestCase
):
    @patch("resolver._links")
    @patch("resolver._get")
    def test_returns_archive_filename_as_version(
        self,
        get_mock,
        links_mock,
    ):
        get_mock.return_value = object()

        links_mock.return_value = [
            (
                "https://www.3gpp.org/ftp/"
                "Specs/archive/38_series/"
                "38.101-1/38101-1-j90.zip"
            ),
            (
                "https://www.3gpp.org/ftp/"
                "Specs/archive/38_series/"
                "38.101-1/38101-1-k00.zip"
            ),
        ]

        reference = Reference(
            raw_text="3GPP TS 38.101-1",
            org="3GPP",
            code="TS 38.101-1",
            title="Range 1 Standalone",
        )

        resolved = _resolve_3gpp(
            reference
        )

        self.assertEqual(
            resolved.source_url,
            (
                "https://www.3gpp.org/ftp/"
                "Specs/archive/38_series/"
                "38.101-1/38101-1-k00.zip"
            ),
        )

        self.assertEqual(
            resolved.version,
            "38101-1-k00.zip",
        )


if __name__ == "__main__":
    unittest.main(
        verbosity=2
    )
