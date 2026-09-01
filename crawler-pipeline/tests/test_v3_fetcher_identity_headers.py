import sys
import unittest
from pathlib import Path


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


from v3_fetcher import (
    _validate_identity,
)

from v3_identity import (
    VersionIdentity,
)


class ThreeGppIdentityHeaderTests(
    unittest.TestCase
):
    def identity(
        self,
        version: str,
    ) -> VersionIdentity:
        return VersionIdentity(
            version=version,
            release=(
                version.split(
                    ".",
                    1,
                )[0]
            ),
            source_filename="spec.zip",
        )

    def test_accepts_standard_3gpp_header(
        self,
    ):
        _validate_identity(
            org="3GPP",
            code="TS 34.108",
            identity=self.identity(
                "15.2.0"
            ),
            document_text=(
                "3GPP TS 34.108 "
                "V15.2.0 (2019-09)"
            ),
        )

    def test_accepts_legacy_3g_header(
        self,
    ):
        _validate_identity(
            org="3GPP",
            code="TS 24.012",
            identity=self.identity(
                "3.0.0"
            ),
            document_text=(
                "3G TS 24.012 "
                "V3.0.0 (1999-09)"
            ),
        )

    def test_accepts_header_without_org_prefix(
        self,
    ):
        _validate_identity(
            org="3GPP",
            code="TS 25.103",
            identity=self.identity(
                "2.0.0"
            ),
            document_text=(
                "TS 25.103 "
                "V2.0.0 (1999-10)"
            ),
        )

    def test_still_rejects_wrong_document_code(
        self,
    ):
        with self.assertRaises(
            ValueError
        ):
            _validate_identity(
                org="3GPP",
                code="TS 25.103",
                identity=self.identity(
                    "2.0.0"
                ),
                document_text=(
                    "TS 25.104 "
                    "V2.0.0 (1999-10)"
                ),
            )


if __name__ == "__main__":
    unittest.main(
        verbosity=2
    )
