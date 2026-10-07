import sqlite3
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
    ),
)

from build_v3_vector_index import (
    build_target_cleanup_where,
    filter_rows,
    load_current_rows,
)


class VectorIndexFilterTests(
    unittest.TestCase
):
    def setUp(
        self,
    ):
        self.rows = [
            {
                "org": "IETF",
                "code": "9113",
                "text": "HTTP/2",
            },
            {
                "org": "IETF",
                "code": "4960",
                "text": "SCTP",
            },
            {
                "org": "3GPP",
                "code": "TS 23.501",
                "text": "5GS",
            },
        ]

    def test_filters_by_org_and_code(
        self,
    ):
        filtered = filter_rows(
            self.rows,
            org="ietf",
            code=" 9113 ",
        )

        self.assertEqual(
            len(
                filtered
            ),
            1,
        )

        self.assertEqual(
            filtered[0]["code"],
            "9113",
        )

    def test_filters_only_by_org(
        self,
    ):
        filtered = filter_rows(
            self.rows,
            org="IETF",
        )

        self.assertEqual(
            len(
                filtered
            ),
            2,
        )

    def test_keeps_all_without_filters(
        self,
    ):
        filtered = filter_rows(
            self.rows
        )

        self.assertEqual(
            filtered,
            self.rows,
        )

    def test_target_cleanup_requires_org_and_code(
        self,
    ):
        self.assertIsNone(
            build_target_cleanup_where(
                org=None,
                code=None,
            )
        )

        self.assertIsNone(
            build_target_cleanup_where(
                org="3GPP",
                code=None,
            )
        )

        self.assertIsNone(
            build_target_cleanup_where(
                org=None,
                code="TS 38.413",
            )
        )

    def test_target_cleanup_is_scoped_to_exact_document(
        self,
    ):
        where = (
            build_target_cleanup_where(
                org="3GPP",
                code="TS 38.413",
            )
        )

        self.assertEqual(
            where,
            {
                "$and": [
                    {
                        "org": {
                            "$eq": "3GPP",
                        }
                    },
                    {
                        "code": {
                            "$eq": "TS 38.413",
                        }
                    },
                ]
            },
        )

    def test_load_current_rows_excludes_historical_versions(
        self,
    ):
        connection = sqlite3.connect(
            ":memory:"
        )

        connection.row_factory = (
            sqlite3.Row
        )

        try:
            connection.executescript(
                """
                CREATE TABLE documents(
                    id TEXT PRIMARY KEY,
                    org TEXT NOT NULL,
                    code TEXT NOT NULL
                );

                CREATE TABLE document_versions(
                    id TEXT PRIMARY KEY,
                    document_id TEXT NOT NULL,
                    version TEXT NOT NULL,
                    release TEXT NOT NULL,
                    source_url TEXT NOT NULL,
                    local_path TEXT NOT NULL,
                    is_latest INTEGER NOT NULL
                );

                CREATE TABLE clauses(
                    id TEXT PRIMARY KEY,
                    version_id TEXT NOT NULL,
                    number TEXT NOT NULL,
                    title TEXT NOT NULL,
                    page_start INTEGER,
                    page_end INTEGER
                );

                CREATE TABLE chunks(
                    id TEXT PRIMARY KEY,
                    clause_id TEXT NOT NULL,
                    chunk_index INTEGER NOT NULL,
                    text TEXT NOT NULL,
                    char_start INTEGER NOT NULL,
                    char_end INTEGER NOT NULL
                );
                """
            )

            connection.execute(
                """
                INSERT INTO documents(
                    id,
                    org,
                    code
                )
                VALUES(
                    'doc-1',
                    '3GPP',
                    'TS 38.413'
                )
                """
            )

            connection.execute(
                """
                INSERT INTO document_versions(
                    id,
                    document_id,
                    version,
                    release,
                    source_url,
                    local_path,
                    is_latest
                )
                VALUES(
                    'ver-old',
                    'doc-1',
                    '19.3.0',
                    '19',
                    'old-url',
                    'old.docx',
                    0
                )
                """
            )

            connection.execute(
                """
                INSERT INTO document_versions(
                    id,
                    document_id,
                    version,
                    release,
                    source_url,
                    local_path,
                    is_latest
                )
                VALUES(
                    'ver-new',
                    'doc-1',
                    '19.4.0',
                    '19',
                    'new-url',
                    'new.docx',
                    1
                )
                """
            )

            connection.execute(
                """
                INSERT INTO clauses(
                    id,
                    version_id,
                    number,
                    title,
                    page_start,
                    page_end
                )
                VALUES(
                    'clause-old',
                    'ver-old',
                    '9.2.8.1',
                    'OLD',
                    NULL,
                    NULL
                )
                """
            )

            connection.execute(
                """
                INSERT INTO clauses(
                    id,
                    version_id,
                    number,
                    title,
                    page_start,
                    page_end
                )
                VALUES(
                    'clause-new',
                    'ver-new',
                    '9.2.8.1',
                    'CURRENT',
                    NULL,
                    NULL
                )
                """
            )

            connection.execute(
                """
                INSERT INTO chunks(
                    id,
                    clause_id,
                    chunk_index,
                    text,
                    char_start,
                    char_end
                )
                VALUES(
                    'chunk-old',
                    'clause-old',
                    0,
                    'old schema',
                    0,
                    10
                )
                """
            )

            connection.execute(
                """
                INSERT INTO chunks(
                    id,
                    clause_id,
                    chunk_index,
                    text,
                    char_start,
                    char_end
                )
                VALUES(
                    'chunk-new',
                    'clause-new',
                    0,
                    'current schema',
                    0,
                    14
                )
                """
            )

            connection.commit()

            rows = load_current_rows(
                connection
            )

            self.assertEqual(
                len(
                    rows
                ),
                1,
            )

            self.assertEqual(
                rows[0]["version"],
                "19.4.0",
            )

            self.assertEqual(
                rows[0]["version_id"],
                "ver-new",
            )

            self.assertEqual(
                rows[0]["text"],
                "current schema",
            )

        finally:
            connection.close()


if __name__ == "__main__":
    unittest.main(
        verbosity=2
    )
