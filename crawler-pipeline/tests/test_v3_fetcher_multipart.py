import io
import unittest
import zipfile

from v3_fetcher import (
    _extract_3gpp_docx_parts,
)


class V3FetcherMultipartTests(
    unittest.TestCase
):
    def _zip(
        self,
        names: list[str],
    ) -> bytes:
        output = io.BytesIO()

        with zipfile.ZipFile(
            output,
            "w",
        ) as archive:
            for name in names:
                archive.writestr(
                    name,
                    name.encode("utf-8"),
                )

        return output.getvalue()

    def test_orders_all_numbered_3gpp_docx_parts(
        self,
    ):
        raw_zip = self._zip(
            [
                (
                    "24501-k00_6_"
                    "Annexes.docx"
                ),
                (
                    "24501-k00_0_"
                    "cover.docx"
                ),
                (
                    "24501-k00_3_"
                    "Main-Body.docx"
                ),
                (
                    "24501-k00_1_"
                    "Main-Body.docx"
                ),
                (
                    "24501-k00_2_"
                    "Main-Body.docx"
                ),
            ]
        )

        parts = (
            _extract_3gpp_docx_parts(
                raw_zip,
                "TS 24.501",
            )
        )

        names = [
            name
            for name, _ in parts
        ]

        self.assertEqual(
            names,
            [
                (
                    "24501-k00_0_"
                    "cover.docx"
                ),
                (
                    "24501-k00_1_"
                    "Main-Body.docx"
                ),
                (
                    "24501-k00_2_"
                    "Main-Body.docx"
                ),
                (
                    "24501-k00_3_"
                    "Main-Body.docx"
                ),
                (
                    "24501-k00_6_"
                    "Annexes.docx"
                ),
            ],
        )

    def test_keeps_single_docx_package_compatible(
        self,
    ):
        raw_zip = self._zip(
            [
                "23040-j00.docx",
            ]
        )

        parts = (
            _extract_3gpp_docx_parts(
                raw_zip,
                "TS 23.040",
            )
        )

        self.assertEqual(
            len(parts),
            1,
        )

        self.assertEqual(
            parts[0][0],
            "23040-j00.docx",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)