import tempfile
import unittest
from pathlib import Path

from v3_catalog import V3Catalog


class V3LatestVersionInvariantTests(
    unittest.TestCase
):
    def setUp(self) -> None:
        self.temp_directory = (
            tempfile.TemporaryDirectory()
        )

        self.catalog = V3Catalog(
            Path(self.temp_directory.name)
            / "catalog.sqlite3"
        )

    def tearDown(self) -> None:
        self.catalog.close()
        self.temp_directory.cleanup()

    def _versions(
        self,
        document_id: str,
    ) -> list[tuple[str, int]]:
        rows = (
            self.catalog.connection.execute(
                """
                SELECT
                    version,
                    is_latest
                FROM document_versions
                WHERE document_id = ?
                ORDER BY version
                """,
                (document_id,),
            ).fetchall()
        )

        return [
            (
                str(row["version"]),
                int(row["is_latest"]),
            )
            for row in rows
        ]

    def test_new_latest_demotes_previous_latest(
        self,
    ) -> None:
        document_id = (
            self.catalog.upsert_document(
                org="3GPP",
                code="TS 38.413",
                title="NGAP",
            )
        )

        self.catalog.upsert_version(
            document_id=document_id,
            version="19.3.0",
            release="19",
            source_url=(
                "https://example.test/"
                "38413-j30.zip"
            ),
            local_path=(
                "documents/ts-38-413/"
                "19.3.0.docx"
            ),
            is_latest=True,
        )

        self.catalog.upsert_version(
            document_id=document_id,
            version="19.4.0",
            release="19",
            source_url=(
                "https://example.test/"
                "38413-j40.zip"
            ),
            local_path=(
                "documents/ts-38-413/"
                "19.4.0.docx"
            ),
            is_latest=True,
        )

        self.assertEqual(
            self._versions(
                document_id
            ),
            [
                ("19.3.0", 0),
                ("19.4.0", 1),
            ],
        )

    def test_historical_upsert_does_not_demote_latest(
        self,
    ) -> None:
        document_id = (
            self.catalog.upsert_document(
                org="3GPP",
                code="TS 38.413",
                title="NGAP",
            )
        )

        self.catalog.upsert_version(
            document_id=document_id,
            version="19.4.0",
            release="19",
            source_url=(
                "https://example.test/"
                "38413-j40.zip"
            ),
            local_path=(
                "documents/ts-38-413/"
                "19.4.0.docx"
            ),
            is_latest=True,
        )

        self.catalog.upsert_version(
            document_id=document_id,
            version="19.3.0",
            release="19",
            source_url=(
                "https://example.test/"
                "38413-j30.zip"
            ),
            local_path=(
                "documents/ts-38-413/"
                "19.3.0.docx"
            ),
            is_latest=False,
        )

        self.assertEqual(
            self._versions(
                document_id
            ),
            [
                ("19.3.0", 0),
                ("19.4.0", 1),
            ],
        )

    def test_latest_change_is_scoped_to_one_document(
        self,
    ) -> None:
        first_document = (
            self.catalog.upsert_document(
                org="3GPP",
                code="TS 38.413",
                title="NGAP",
            )
        )

        second_document = (
            self.catalog.upsert_document(
                org="3GPP",
                code="TS 23.041",
                title="CBS",
            )
        )

        self.catalog.upsert_version(
            document_id=first_document,
            version="19.3.0",
            release="19",
            source_url="https://example.test/a",
            local_path="a.docx",
            is_latest=True,
        )

        self.catalog.upsert_version(
            document_id=second_document,
            version="20.0.0",
            release="20",
            source_url="https://example.test/b",
            local_path="b.docx",
            is_latest=True,
        )

        self.catalog.upsert_version(
            document_id=first_document,
            version="19.4.0",
            release="19",
            source_url="https://example.test/c",
            local_path="c.docx",
            is_latest=True,
        )

        self.assertEqual(
            self._versions(
                second_document
            ),
            [
                ("20.0.0", 1),
            ],
        )


if __name__ == "__main__":
    unittest.main()
