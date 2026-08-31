"""Doğrulanan üç farklı kaynağı V3 pilot kataloğa aktarır."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
from pathlib import Path
import re
import shutil
import sys


BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR / "src"))

from v3_catalog import V3Catalog
from v3_ingestor import V3DocumentInput, ingest_document


@dataclass(frozen=True)
class PilotSource:
    label: str
    org: str
    code: str
    title: str
    version: str
    release: str
    source_url: str
    directory_pattern: str
    primary_pattern: str
    package_pattern: str


SOURCES = (
    PilotSource(
        label="3GPP TS 23.040",
        org="3GPP",
        code="TS 23.040",
        title=(
            "Technical realization of the "
            "Short Message Service (SMS)"
        ),
        version="19.0.0",
        release="19",
        source_url=(
            "https://www.3gpp.org/ftp/Specs/archive/"
            "23_series/23.040/23040-j00.zip"
        ),
        directory_pattern=(
            "documents/3gpp/ts-23-040/*"
        ),
        primary_pattern="*.docx",
        package_pattern="*.zip",
    ),
    PilotSource(
        label="IETF RFC 4960",
        org="IETF",
        code="4960",
        title=(
            "Stream Control Transmission Protocol"
        ),
        version="RFC 4960",
        release="",
        source_url=(
            "https://www.rfc-editor.org/"
            "rfc/rfc4960.html"
        ),
        directory_pattern=(
            "documents/ietf/4960/*"
        ),
        primary_pattern="*.html",
        package_pattern="*.html",
    ),
    PilotSource(
        label="ETSI TS 102 900",
        org="ETSI",
        code="TS 102 900",
        title=(
            "European Public Warning System "
            "(EU-ALERT) using CBS"
        ),
        version="1.4.1",
        release="",
        source_url=(
            "https://www.etsi.org/deliver/"
            "etsi_ts/102900_102999/102900/"
            "01.04.01_60/"
            "ts_102900v010401p.pdf"
        ),
        directory_pattern=(
            "documents/etsi/ts-102-900/*"
        ),
        primary_pattern="*.pdf",
        package_pattern="*.pdf",
    ),
)


def _find_one(
    root: Path,
    pattern: str,
) -> Path:
    matches = [
        path
        for path in root.glob(pattern)
        if path.exists()
    ]

    matches.sort(
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )

    if not matches:
        raise FileNotFoundError(
            f"Bulunamadı: {root / pattern}"
        )

    return matches[0]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as file:
        for block in iter(
            lambda: file.read(1024 * 1024),
            b"",
        ):
            digest.update(block)

    return digest.hexdigest()


def _page_texts(
    document_text: str,
) -> tuple[str, ...]:
    marker = re.compile(
        r"(?m)^\s*\[\[PAGE:(\d+)\]\]\s*$"
    )

    matches = list(
        marker.finditer(document_text)
    )

    if not matches:
        return ()

    pages: list[str] = []

    for index, match in enumerate(matches):
        if index + 1 < len(matches):
            end = matches[index + 1].start()
        else:
            end = len(document_text)

        page_text = document_text[
            match.end():end
        ].strip()

        pages.append(page_text)

    return tuple(pages)


def _copy_source_directory(
    *,
    source_root: Path,
    catalog_root: Path,
    source: PilotSource,
) -> tuple[Path, Path, Path]:
    source_directory = _find_one(
        source_root,
        source.directory_pattern,
    )

    relative_directory = (
        source_directory.relative_to(source_root)
    )

    target_directory = (
        catalog_root / relative_directory
    )

    shutil.copytree(
        source_directory,
        target_directory,
        dirs_exist_ok=True,
    )

    extracted_path = (
        target_directory / "extracted.txt"
    )

    if not extracted_path.exists():
        raise FileNotFoundError(
            "Çıkarılmış metin bulunamadı: "
            f"{extracted_path}"
        )

    primary_path = _find_one(
        target_directory,
        source.primary_pattern,
    )

    package_path = _find_one(
        target_directory,
        source.package_pattern,
    )

    return (
        extracted_path,
        primary_path,
        package_path,
    )


def _print_catalog_summary(
    catalog: V3Catalog,
) -> None:
    print("\n" + "=" * 76)
    print("CATALOG SUMMARY")

    tables = (
        "documents",
        "document_versions",
        "clauses",
        "chunks",
        "reference_edges",
    )

    for table in tables:
        count = catalog.connection.execute(
            f"SELECT COUNT(*) FROM {table}"
        ).fetchone()[0]

        print(f"{table}: {count}")

    print("\nREFERENCE KINDS:")

    rows = catalog.connection.execute(
        """
        SELECT
            reference_kind,
            COUNT(*) AS total
        FROM reference_edges
        GROUP BY reference_kind
        ORDER BY reference_kind
        """
    ).fetchall()

    for row in rows:
        print(
            f"{row['reference_kind']}: "
            f"{row['total']}"
        )

    print("\nINGESTED VERSION CONTENT:")

    rows = catalog.connection.execute(
        """
        SELECT
            d.org,
            d.code,
            v.version,
            COUNT(DISTINCT c.id) AS clauses,
            COUNT(DISTINCT ch.id) AS chunks
        FROM document_versions AS v
        JOIN documents AS d
            ON d.id = v.document_id
        LEFT JOIN clauses AS c
            ON c.version_id = v.id
        LEFT JOIN chunks AS ch
            ON ch.clause_id = c.id
        GROUP BY v.id
        ORDER BY d.org, d.code
        """
    ).fetchall()

    for row in rows:
        print(
            f"{row['org']} {row['code']} | "
            f"{row['version']} | "
            f"clauses={row['clauses']} | "
            f"chunks={row['chunks']}"
        )

    linked = catalog.connection.execute(
        """
        SELECT COUNT(*)
        FROM reference_edges AS e
        WHERE EXISTS (
            SELECT 1
            FROM document_versions AS v
            WHERE v.document_id =
                  e.target_document_id
        )
        """
    ).fetchone()[0]

    print(
        "\nEDGES WITH FETCHED TARGET VERSION:",
        linked,
    )


def main() -> None:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--source-dir",
        required=True,
    )

    parser.add_argument(
        "--catalog-dir",
        required=True,
    )

    args = parser.parse_args()

    source_root = Path(
        args.source_dir
    ).resolve()

    catalog_root = Path(
        args.catalog_dir
    ).resolve()

    catalog_path = (
        catalog_root / "catalog.sqlite3"
    )

    if not catalog_path.exists():
        raise FileNotFoundError(
            "Pilot katalog bulunamadı: "
            f"{catalog_path}"
        )

    catalog = V3Catalog(catalog_path)

    try:
        for source in SOURCES:
            (
                extracted_path,
                primary_path,
                package_path,
            ) = _copy_source_directory(
                source_root=source_root,
                catalog_root=catalog_root,
                source=source,
            )

            document_text = (
                extracted_path.read_text(
                    encoding="utf-8"
                )
            )

            pages = _page_texts(document_text)

            result = ingest_document(
                catalog=catalog,
                document=V3DocumentInput(
                    org=source.org,
                    code=source.code,
                    title=source.title,
                    version=source.version,
                    release=source.release,
                    source_url=source.source_url,
                    local_path=(
                        primary_path
                        .relative_to(catalog_root)
                        .as_posix()
                    ),
                    content_sha256=(
                        _sha256(package_path)
                    ),
                    document_text=document_text,
                    page_texts=pages,
                ),
            )

            print("\n" + "=" * 76)
            print("INGESTED:", source.label)
            print("VERSION:", source.version)
            print(
                "CLAUSES:",
                result.clause_count,
            )
            print(
                "CHUNKS:",
                result.chunk_count,
            )
            print(
                "REFERENCES:",
                result.reference_count,
            )
            print("PAGES:", len(pages))
            print(
                "LOCAL:",
                primary_path
                .relative_to(catalog_root)
                .as_posix(),
            )

        _print_catalog_summary(catalog)

    finally:
        catalog.close()

    print(
        "\nMULTISOURCE V3 INGEST COMPLETE"
    )


if __name__ == "__main__":
    main()