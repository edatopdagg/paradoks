import unittest

from v3_identity import (
    infer_version_identity,
)


class V3VersionIdentityTests(unittest.TestCase):
    def test_reads_3gpp_version_19(self) -> None:
        identity = infer_version_identity(
            org="3GPP",
            code="TS 23.040",
            source_url=(
                "https://www.3gpp.org/ftp/"
                "Specs/archive/23_series/"
                "23.040/23040-j00.zip"
            ),
        )

        self.assertEqual(
            identity.version,
            "19.0.0",
        )
        self.assertEqual(
            identity.release,
            "19",
        )

    def test_reads_3gpp_version_20(self) -> None:
        identity = infer_version_identity(
            org="3GPP",
            code="TS 23.041",
            source_url=(
                "https://www.3gpp.org/ftp/"
                "Specs/archive/23_series/"
                "23.041/23041-k00.zip"
            ),
        )

        self.assertEqual(
            identity.version,
            "20.0.0",
        )
        self.assertEqual(
            identity.release,
            "20",
        )

    def test_reads_3gpp_minor_version(self) -> None:
        identity = infer_version_identity(
            org="3GPP",
            code="TS 23.041",
            source_url=(
                "https://example.test/"
                "23041-k10.zip"
            ),
        )

        self.assertEqual(
            identity.version,
            "20.1.0",
        )


    def test_reads_multipart_3gpp_version(
        self,
    ) -> None:
        identity = infer_version_identity(
            org="3GPP",
            code="TS 38.101-1",
            source_url=(
                "https://www.3gpp.org/ftp/"
                "Specs/archive/38_series/"
                "38.101-1/38101-1-k00.zip"
            ),
        )

        self.assertEqual(
            identity.version,
            "20.0.0",
        )
        self.assertEqual(
            identity.release,
            "20",
        )
        self.assertEqual(
            identity.source_filename,
            "38101-1-k00.zip",
        )

    def test_rejects_wrong_multipart_archive(
        self,
    ) -> None:
        with self.assertRaises(
            ValueError
        ):
            infer_version_identity(
                org="3GPP",
                code="TS 38.101-1",
                source_url=(
                    "https://www.3gpp.org/ftp/"
                    "Specs/archive/38_series/"
                    "38.101-2/38101-2-k00.zip"
                ),
            )

    def test_reads_etsi_version(self) -> None:
        identity = infer_version_identity(
            org="ETSI",
            code="TS 102 900",
            source_url=(
                "https://www.etsi.org/"
                "ts_102900v010401p.pdf"
            ),
        )

        self.assertEqual(
            identity.version,
            "1.4.1",
        )
        self.assertEqual(
            identity.release,
            "",
        )

    def test_uses_rfc_identity_as_version(self) -> None:
        identity = infer_version_identity(
            org="IETF",
            code="4960",
            source_url=(
                "https://www.rfc-editor.org/"
                "rfc/rfc4960.html"
            ),
        )

        self.assertEqual(
            identity.version,
            "RFC 4960",
        )
        self.assertEqual(
            identity.release,
            "",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)