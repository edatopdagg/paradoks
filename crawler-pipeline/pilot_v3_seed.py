import argparse
import hashlib
import re
import shutil
import sys
from collections import OrderedDict
from pathlib import Path

from docx import Document


BASE_DIR = Path(__file__).resolve().parent
SRC_DIR = BASE_DIR / "src"
sys.path.insert(0, str(SRC_DIR))

from chunker import build_chunks
from reference_parser import parse_references_section
from v3_catalog import V3Catalog


def _read_docx_paragraphs(path: Path) -> list[str]:
    document = Document(str(path))
    return [
        paragraph.text.strip()
        for paragraph in document.paragraphs
        if paragraph.text.strip()
    ]


def _parse_3gpp_identity(paragraphs: list[str]) -> dict[str, str]:
    head = "\n".join(paragraphs[:80])
    match = re.search(
        r"3GPP\s+(TS|TR)\s+(\d{2}\.\d{3})\s+"
        r"V(\d+\.\d+\.\d+)\s+\((\d{4}-\d{2})\)",
        head,
        flags=re.IGNORECASE,
    )
    if not match:
        raise ValueError("Seed dosyasından 3GPP kimliği okunamadı.")

    release_match = re.search(r"\(Release\s+(\d+)\)", head, flags=re.IGNORECASE)
    title = next(
        (
            paragraph
            for paragraph in paragraphs[:30]
            if paragraph.casefold().startswith("technical reali")
        ),
        "",
    )

    return {
        "org": "3GPP",
        "code": f"{match.group(1).upper()} {match.group(2)}",
        "version": match.group(3),
        "publication_date": match.group(4),
        "release": release_match.group(1) if release_match else "",
        "title": title,
    }


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _official_3gpp_url(code: str, filename: str) -> str:
    number = code.split()[-1]
    series = number.split(".")[0]
    return (
        f"https://www.3gpp.org/ftp/Specs/archive/"
        f"{series}_series/{number}/{Path(filename).stem}.zip"
    )


def run_pilot(seed_path: Path, output_dir: Path) -> None:
    seed_path = seed_path.resolve()
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    paragraphs = _read_docx_paragraphs(seed_path)
    document_text = "\n".join(paragraphs)
    identity = _parse_3gpp_identity(paragraphs)

    document_directory = (
        output_dir
        / "documents"
        / _slug(identity["org"])
        / _slug(identity["code"])
        / identity["version"]
    )
    document_directory.mkdir(parents=True, exist_ok=True)
    stored_document_path = document_directory / seed_path.name
    shutil.copy2(seed_path, stored_document_path)
    relative_document_path = stored_document_path.relative_to(output_dir).as_posix()

    source_url = _official_3gpp_url(identity["code"], seed_path.name)
    catalog = V3Catalog(output_dir / "catalog.sqlite3")

    try:
        document_id = catalog.upsert_document(
            org=identity["org"],
            code=identity["code"],
            title=identity["title"],
        )
        version_id = catalog.upsert_version(
            document_id=document_id,
            version=identity["version"],
            release=identity["release"],
            source_url=source_url,
            local_path=relative_document_path,
            content_sha256=_sha256(stored_document_path),
            is_latest=True,
        )

        chunks = build_chunks(
            document_text=document_text,
            doc_org=identity["org"],
            doc_code=identity["code"],
            version=identity["version"],
            source_url=source_url,
        )

        grouped_clauses: OrderedDict[str, dict] = OrderedDict()
        for chunk in chunks:
            clause_number = (chunk.clause or "document").strip()
            group = grouped_clauses.setdefault(
                clause_number,
                {"title": (chunk.clause_title or "").strip(), "chunks": []},
            )
            group["chunks"].append((chunk.text or "").strip())

        clause_ids: dict[str, str] = {}
        chunk_count = 0

        for clause_number, clause_data in grouped_clauses.items():
            chunk_texts = [text for text in clause_data["chunks"] if text]
            body_text = "\n\n".join(chunk_texts)
            clause_id = catalog.upsert_clause(
                version_id=version_id,
                number=clause_number,
                title=clause_data["title"],
                body_text=body_text,
                page_start=None,
                page_end=None,
            )
            clause_ids[clause_number] = clause_id

            cursor = 0
            for chunk_index, chunk_text in enumerate(chunk_texts):
                if chunk_index:
                    cursor += 2
                char_start = cursor
                char_end = char_start + len(chunk_text)
                catalog.upsert_chunk(
                    clause_id=clause_id,
                    text=chunk_text,
                    chunk_index=chunk_index,
                    char_start=char_start,
                    char_end=char_end,
                )
                cursor = char_end
                chunk_count += 1

        references = parse_references_section(document_text)
        reference_clause_id = clause_ids.get("1.1")
        for reference in references:
            target_document_id = catalog.upsert_document(
                org=reference.org,
                code=reference.code,
                title=reference.title,
            )
            catalog.upsert_reference(
                source_version_id=version_id,
                source_clause_id=reference_clause_id,
                target_document_id=target_document_id,
                target_org=reference.org,
                target_code=reference.code,
                ref_number=reference.ref_number,
                raw_text=reference.raw_text,
            )

        print("PILOT V3 TAMAMLANDI")
        print("Belge:", identity["org"], identity["code"])
        print("Surum:", identity["version"])
        print("Release:", identity["release"])
        print("Yayin tarihi:", identity["publication_date"])
        print("Madde:", len(grouped_clauses))
        print("Chunk:", chunk_count)
        print("Referans kenari:", len(references))
        print("Katalog:", output_dir / "catalog.sqlite3")
        print("Orijinal belge:", stored_document_path)
    finally:
        catalog.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Paradoks V3 seed pilot importer")
    parser.add_argument("--seed", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    run_pilot(Path(args.seed), Path(args.output_dir))


if __name__ == "__main__":
    main()
