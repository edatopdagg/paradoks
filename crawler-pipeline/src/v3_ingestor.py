"""İndirilen standart belgesini V3 kataloğa kaydeder."""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
import re

from chunker import build_chunks
from v3_catalog import V3Catalog
from v3_reference_parser import parse_v3_references


@dataclass(frozen=True)
class V3DocumentInput:
    org: str
    code: str
    title: str
    version: str
    release: str
    source_url: str
    local_path: str
    content_sha256: str
    document_text: str
    page_texts: tuple[str, ...] = ()


@dataclass(frozen=True)
class V3IngestResult:
    document_id: str
    version_id: str
    clause_count: int
    chunk_count: int
    reference_count: int


def _normalized(value: str) -> str:
    return re.sub(
        r"\s+",
        " ",
        value or "",
    ).strip().casefold()


def _content_needles(text: str) -> list[str]:
    lines = [
        _normalized(line)
        for line in (text or "").splitlines()
    ]

    useful = [
        line
        for line in lines[1:]
        if len(line) >= 40
    ]

    if not useful:
        useful = [
            line
            for line in lines
            if len(line) >= 20
        ]

    return useful


def _prepare_document_text(
    org: str,
    document_text: str,
) -> str:
    if (
        org or ""
    ).strip().upper() != "ETSI":
        return document_text

    cleaned_lines: list[str] = []

    running_header = re.compile(
        r"^\s*\d+\s+ETSI\s+"
        r"(?:TS|TR|EN)\s+"
        r"\d{3}\s*\d{3}\s+"
        r"V\d+\.\d+\.\d+",
        re.IGNORECASE,
    )

    page_marker = re.compile(
        r"^\s*\[\[PAGE:\d+\]\]\s*$",
        re.IGNORECASE,
    )

    date_continuation = re.compile(
        r"^\d{1,2}\s+"
        r"(?:January|February|March|April|May|June|"
        r"July|August|September|October|November|December)"
        r"\s+\d{4}\.?\s*$",
        re.IGNORECASE,
    )

    for line in (
        document_text or ""
    ).splitlines():
        stripped = line.strip()

        if page_marker.match(stripped):
            continue

        if running_header.match(stripped):
            continue

        if stripped.casefold() in {
            "etsi",
            "contents",
        }:
            continue

        if re.search(
            r"\.{5,}",
            stripped,
        ):
            continue

        # Örneğin "31 January 2018." önceki
        # bibliyografik kaydın devamıdır. Başlık
        # olarak algılanmaması için girintili tutulur.
        if date_continuation.match(stripped):
            cleaned_lines.append(
                f" {stripped}"
            )
            continue

        cleaned_lines.append(line)

    # ETSI ön sayfaları ve İçindekiler bölümü
    # gerçek "1 Scope" maddesinden önce bulunur.
    # Son gerçek Scope başlangıcından öncesini atar.
    scope_starts = [
        index
        for index, line in enumerate(
            cleaned_lines
        )
        if re.fullmatch(
            r"\s*1\s+Scope\s*",
            line,
            flags=re.IGNORECASE,
        )
    ]

    if scope_starts:
        cleaned_lines = cleaned_lines[
            scope_starts[-1]:
        ]

    return "\n".join(cleaned_lines)


def _pages_for_text(
    text: str,
    page_texts: tuple[str, ...],
) -> list[int]:
    if not page_texts:
        return []

    normalized_pages = [
        _normalized(page)
        for page in page_texts
    ]

    candidates: list[
        tuple[int, list[int]]
    ] = []

    for line in _content_needles(text):
        needle = line[:180]

        found = [
            page_number
            for page_number, page in enumerate(
                normalized_pages,
                start=1,
            )
            if needle in page
        ]

        if found:
            candidates.append(
                (len(found), found)
            )

    if not candidates:
        return []

    best_frequency = min(
        frequency
        for frequency, _ in candidates
    )

    # Başlık hem İçindekiler sayfasında
    # hem gerçek belge gövdesinde bulunursa
    # son geçtiği sayfayı seçer.
    if best_frequency > 1:
        repeated_pages = [
            page_number
            for frequency, found in candidates
            if frequency == best_frequency
            for page_number in found
        ]

        if repeated_pages:
            return [max(repeated_pages)]

    pages: list[int] = []

    for frequency, found in candidates:
        if frequency != best_frequency:
            continue

        for page_number in found:
            if page_number not in pages:
                pages.append(page_number)

    return pages

def _page_range(
    chunk_texts: list[str],
    page_texts: tuple[str, ...],
) -> tuple[int | None, int | None]:
    pages = [
        page
        for chunk_text in chunk_texts
        for page in _pages_for_text(
            chunk_text,
            page_texts,
        )
    ]

    if not pages:
        return None, None

    return min(pages), max(pages)


def _reference_clause_id(
    grouped_clauses: OrderedDict[str, dict],
    clause_ids: dict[str, str],
) -> str | None:
    candidates: list[
        tuple[str, dict]
    ] = []

    for number, data in (
        grouped_clauses.items()
    ):
        title = _normalized(
            data["title"]
        )

        if "reference" in title:
            candidates.append(
                (number, data)
            )

    if not candidates:
        return None

    candidates.sort(
        key=lambda item: sum(
            len(text)
            for text in item[1]["chunks"]
        ),
        reverse=True,
    )

    return clause_ids.get(
        candidates[0][0]
    )


def ingest_document(
    *,
    catalog: V3Catalog,
    document: V3DocumentInput,
) -> V3IngestResult:
    document_id = catalog.upsert_document(
        org=document.org,
        code=document.code,
        title=document.title,
    )

    version_id = catalog.upsert_version(
        document_id=document_id,
        version=document.version,
        release=document.release,
        source_url=document.source_url,
        local_path=document.local_path,
        content_sha256=document.content_sha256,
        is_latest=True,
    )

    prepared_text = _prepare_document_text(
        document.org,
        document.document_text,
    )

    chunks = build_chunks(
        document_text=prepared_text,
        doc_org=document.org,
        doc_code=document.code,
        version=document.version,
        source_url=document.source_url,
    )

    grouped_clauses: OrderedDict[
        str,
        dict,
    ] = OrderedDict()

    for chunk in chunks:
        clause_number = (
            chunk.clause or "document"
        ).strip()

        group = grouped_clauses.setdefault(
            clause_number,
            {
                "title": (
                    chunk.clause_title or ""
                ).strip(),
                "chunks": [],
            },
        )

        clean_text = (
            chunk.text or ""
        ).strip()

        if clean_text:
            group["chunks"].append(
                clean_text
            )

    references = parse_v3_references(
        document.org,
        document.document_text,
    )

    # Aynı sürüm tekrar işleniyorsa yalnızca
    # o sürümün eski türetilmiş kayıtlarını
    # temizler. Diğer belgeler korunur.
    catalog.connection.execute(
        """
        DELETE FROM reference_edges
        WHERE source_version_id = ?
        """,
        (version_id,),
    )

    catalog.connection.execute(
        """
        DELETE FROM chunks
        WHERE clause_id IN (
            SELECT id
            FROM clauses
            WHERE version_id = ?
        )
        """,
        (version_id,),
    )

    catalog.connection.execute(
        """
        DELETE FROM clauses
        WHERE version_id = ?
        """,
        (version_id,),
    )

    catalog.connection.commit()

    clause_ids: dict[str, str] = {}
    chunk_count = 0

    for (
        clause_number,
        clause_data,
    ) in grouped_clauses.items():
        chunk_texts = (
            clause_data["chunks"]
        )

        body_text = "\n\n".join(
            chunk_texts
        )

        (
            page_start,
            page_end,
        ) = _page_range(
            chunk_texts,
            document.page_texts,
        )

        clause_id = catalog.upsert_clause(
            version_id=version_id,
            number=clause_number,
            title=clause_data["title"],
            body_text=body_text,
            page_start=page_start,
            page_end=page_end,
        )

        clause_ids[
            clause_number
        ] = clause_id

        cursor = 0

        for (
            chunk_index,
            chunk_text,
        ) in enumerate(chunk_texts):
            if chunk_index:
                cursor += 2

            char_start = cursor
            char_end = (
                char_start +
                len(chunk_text)
            )

            catalog.upsert_chunk(
                clause_id=clause_id,
                text=chunk_text,
                chunk_index=chunk_index,
                char_start=char_start,
                char_end=char_end,
            )

            cursor = char_end
            chunk_count += 1

    reference_clause_id = (
        _reference_clause_id(
            grouped_clauses,
            clause_ids,
        )
    )

    for reference in references:
        target_document_id = (
            catalog.upsert_document(
                org=reference.org,
                code=reference.code,
                title=reference.title,
            )
        )

        catalog.upsert_reference(
            source_version_id=version_id,
            source_clause_id=(
                reference_clause_id
            ),
            target_document_id=(
                target_document_id
            ),
            target_org=reference.org,
            target_code=reference.code,
            ref_number=(
                reference.ref_number
            ),
            raw_text=reference.raw_text,
            reference_kind=(
                reference.reference_kind
            ),
        )

    return V3IngestResult(
        document_id=document_id,
        version_id=version_id,
        clause_count=len(
            grouped_clauses
        ),
        chunk_count=chunk_count,
        reference_count=len(
            references
        ),
    )