import sqlite3
import tempfile
from pathlib import Path

from app.services.retriever import (
    Retriever,
)


def _create_catalog(
    path: Path,
) -> None:

    connection = sqlite3.connect(
        str(path)
    )

    connection.executescript(
        """
        CREATE TABLE documents (
            id TEXT PRIMARY KEY,
            org_key TEXT NOT NULL,
            code_key TEXT NOT NULL
        );

        CREATE TABLE document_versions (
            id TEXT PRIMARY KEY,
            document_id TEXT NOT NULL,
            is_latest INTEGER NOT NULL
        );

        INSERT INTO documents(
            id,
            org_key,
            code_key
        )
        VALUES (
            'doc-1',
            '3gpp',
            'ts 38.413'
        );

        INSERT INTO document_versions(
            id,
            document_id,
            is_latest
        )
        VALUES (
            'version-old',
            'doc-1',
            1
        );
        """
    )

    connection.commit()
    connection.close()


def test_catalog_change_invalidates_latest_version_cache():

    with tempfile.TemporaryDirectory() as directory:

        catalog_path = (
            Path(directory)
            / "catalog.sqlite3"
        )

        _create_catalog(
            catalog_path
        )

        retriever = Retriever.__new__(
            Retriever
        )

        retriever._document_where_cache = {}
        retriever._document_where_cache_signature = None

        retriever._resolve_catalog_path = (
            lambda: catalog_path
        )

        signature = [
            (
                "catalog",
                1,
            )
        ]

        retriever._catalog_cache_signature = (
            lambda _:
                signature[0]
        )

        where = {
            "$and": [
                {
                    "org":
                        "3GPP",
                },
                {
                    "code":
                        "TS 38.413",
                },
            ]
        }

        first = (
            retriever
            ._resolve_fast_document_where(
                where
            )
        )

        assert first == {
            "version_id":
                "version-old"
        }

        connection = sqlite3.connect(
            str(catalog_path)
        )

        connection.executescript(
            """
            UPDATE document_versions
            SET is_latest = 0
            WHERE id = 'version-old';

            INSERT INTO document_versions(
                id,
                document_id,
                is_latest
            )
            VALUES (
                'version-new',
                'doc-1',
                1
            );
            """
        )

        connection.commit()
        connection.close()

        # Simulate catalog/WAL filesystem change.
        signature[0] = (
            "catalog",
            2,
        )

        second = (
            retriever
            ._resolve_fast_document_where(
                where
            )
        )

        assert second == {
            "version_id":
                "version-new"
        }


def test_catalog_signature_tracks_main_and_wal_files():

    with tempfile.TemporaryDirectory() as directory:

        catalog_path = (
            Path(directory)
            / "catalog.sqlite3"
        )

        catalog_path.write_bytes(
            b"catalog"
        )

        wal_path = Path(
            str(catalog_path)
            + "-wal"
        )

        wal_path.write_bytes(
            b"wal"
        )

        signature = (
            Retriever
            ._catalog_cache_signature(
                catalog_path
            )
        )

        names = {
            item[0]
            for item
            in signature
        }

        assert catalog_path.name in names
        assert wal_path.name in names
