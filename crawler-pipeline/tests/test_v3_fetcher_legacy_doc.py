import io
import unittest
import zipfile
from unittest.mock import patch

from v3_fetcher import (
    _extract_3gpp_docx_parts,
    _read_legacy_doc_bytes,
)


class V3FetcherLegacyDocTests(
    unittest.TestCase
):
    def test_extracts_legacy_doc_from_3gpp_zip(
        self,
    ):
        buffer = io.BytesIO()

        with zipfile.ZipFile(
            buffer,
            mode="w",
        ) as archive:
            archive.writestr(
                "45002-j00.doc",
                b"legacy-word-content",
            )
            archive.writestr(
                "readme.txt",
                b"ignore-this",
            )

        parts = _extract_3gpp_docx_parts(
            buffer.getvalue(),
            "TS 45.002",
        )

        self.assertEqual(
            len(parts),
            1,
        )
        self.assertEqual(
            parts[0][0],
            "45002-j00.doc",
        )
        self.assertEqual(
            parts[0][1],
            b"legacy-word-content",
        )

    @patch(
        "v3_fetcher.subprocess.run"
    )
    @patch(
        "v3_fetcher.shutil.which",
        return_value="antiword",
    )
    def test_reads_legacy_doc_with_antiword(
        self,
        which_mock,
        run_mock,
    ):
        run_mock.return_value.returncode = 0
        run_mock.return_value.stdout = (
            b"Legacy telecom standard text"
        )
        run_mock.return_value.stderr = b""

        result = _read_legacy_doc_bytes(
            b"legacy-word-binary",
        )

        self.assertEqual(
            result,
            "Legacy telecom standard text",
        )

        which_mock.assert_called_once_with(
            "antiword"
        )

        command = (
            run_mock.call_args.args[0]
        )

        self.assertEqual(
            command[0:3],
            [
                "antiword",
                "-m",
                "UTF-8.txt",
            ],
        )

    @patch(
        "v3_fetcher.shutil.which",
        return_value=None,
    )
    def test_reports_missing_antiword(
        self,
        which_mock,
    ):
        with self.assertRaisesRegex(
            RuntimeError,
            "antiword",
        ):
            _read_legacy_doc_bytes(
                b"legacy-word-binary",
            )

        which_mock.assert_called_once_with(
            "antiword"
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
