"""İndirilen standart belgesini V3 kataloğa kaydeder."""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
import re

from chunker import build_chunks
from v3_catalog import V3Catalog, _stable_id
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


def _canonicalize_3gpp_reference(
    catalog: V3Catalog,
    org: str,
    code: str,
) -> tuple[str, str]:
    """
    3GPP kaynak belgelerinde TS/TR türü yanlış yazılmış
    referansları, katalogda doğrulanmış karşı kimlik varsa
    canonical belgeye yönlendirir.

    Örnek:
        kaynak: TR 38.101-4
        gerçek/indexed: TS 38.101-4
        sonuç: TS 38.101-4

    Güvenlik:
    - Yalnız 3GPP TS/TR kodlarında çalışır.
    - Aynı numarayı korur.
    - İstenen kimlik zaten indekslenmişse değiştirmez.
    - Karşı tür gerçekten document_versions içeriyorsa
      canonical kabul eder.
    """

    org_value = re.sub(
        r"\s+",
        " ",
        org or "",
    ).strip().upper()

    code_value = re.sub(
        r"\s+",
        " ",
        code or "",
    ).strip().upper()

    if org_value != "3GPP":
        return org_value, code_value

    match = re.fullmatch(
        r"(TS|TR)\s+"
        r"(\d{2}\.\d{3}(?:-\d+)?)",
        code_value,
    )

    if match is None:
        return org_value, code_value

    # İstenen kimliğin kendisi gerçek bir sürüm içeriyorsa
    # artık doğrulanmıştır; karşı türe çevrilmez.
    current_verified = catalog.connection.execute(
        """
        SELECT 1
        FROM documents d

        JOIN document_versions dv
          ON dv.document_id = d.id

        WHERE d.org = '3GPP'
          AND d.code = ?

        LIMIT 1
        """,
        (code_value,),
    ).fetchone()

    if current_verified is not None:
        return org_value, code_value

    requested_type = match.group(1)
    number = match.group(2)

    opposite_type = (
        "TR"
        if requested_type == "TS"
        else "TS"
    )

    opposite_code = (
        f"{opposite_type} {number}"
    )

    # Yalnız gerçekten indekslenmiş karşı kimlik
    # canonical kabul edilir.
    canonical = catalog.connection.execute(
        """
        SELECT
            d.code
        FROM documents d

        WHERE d.org = '3GPP'
          AND d.code = ?
          AND EXISTS (
              SELECT 1
              FROM document_versions dv
              WHERE dv.document_id = d.id
          )

        LIMIT 1
        """,
        (opposite_code,),
    ).fetchone()

    if canonical is None:
        return org_value, code_value

    return (
        "3GPP",
        canonical["code"],
    )


def _repair_opposite_3gpp_alias(
    catalog: V3Catalog,
    *,
    canonical_document_id: str,
    org: str,
    code: str,
) -> int:
    """
    Gerçek 3GPP TS/TR belgesi başarıyla indekslendikten sonra,
    aynı numarada daha önce oluşmuş doğrulanmamış karşı-tür
    alias kaydını canonical belgeye birleştirir.

    Örnek:
        önce: TR 38.101-4 alias oluştu
        sonra: TS 38.101-4 gerçekten indekslendi

        sonuç:
        - eski TR edge'leri TS document'a taşınır
        - raw_text korunur
        - deterministik canonical edge id üretilir
        - crawl depth kaybolmaz
        - alias crawl job silinir
        - alias document silinir

    Güvenlik:
    - yalnız 3GPP TS/TR için çalışır
    - numara değişmez
    - canonical belge gerçekten version içermelidir
    - alias'ın version'ı varsa merge yapılmaz
    """

    connection = catalog.connection

    org_value = re.sub(
        r"\s+",
        " ",
        org or "",
    ).strip().upper()

    code_value = re.sub(
        r"\s+",
        " ",
        code or "",
    ).strip().upper()

    if org_value != "3GPP":
        return 0

    match = re.fullmatch(
        r"(TS|TR)\s+"
        r"(\d{2}\.\d{3}(?:-\d+)?)",
        code_value,
    )

    if match is None:
        return 0

    # Canonical belge gerçekten indekslenmiş olmalı.
    canonical_version = connection.execute(
        """
        SELECT
            source_url
        FROM document_versions
        WHERE document_id = ?
        ORDER BY
            is_latest DESC,
            rowid DESC
        LIMIT 1
        """,
        (canonical_document_id,),
    ).fetchone()

    if canonical_version is None:
        return 0

    canonical_type = match.group(1)
    number = match.group(2)

    opposite_type = (
        "TR"
        if canonical_type == "TS"
        else "TS"
    )

    alias_code = (
        f"{opposite_type} {number}"
    )

    alias = connection.execute(
        """
        SELECT
            id,
            code
        FROM documents
        WHERE org = '3GPP'
          AND code = ?
          AND id <> ?
        LIMIT 1
        """,
        (
            alias_code,
            canonical_document_id,
        ),
    ).fetchone()

    if alias is None:
        return 0

    alias_document_id = alias["id"]

    # Karşı tür de gerçekten indekslenmişse iki doğrulanmış
    # belge vardır; otomatik merge yapma.
    alias_has_version = connection.execute(
        """
        SELECT 1
        FROM document_versions
        WHERE document_id = ?
        LIMIT 1
        """,
        (alias_document_id,),
    ).fetchone()

    if alias_has_version is not None:
        return 0

    crawl_jobs_exists = (
        connection.execute(
            """
            SELECT 1
            FROM sqlite_master
            WHERE type = 'table'
              AND name = 'crawl_jobs'
            """
        ).fetchone()
        is not None
    )

    alias_edges = connection.execute(
        """
        SELECT *
        FROM reference_edges
        WHERE target_document_id = ?
        ORDER BY id
        """,
        (alias_document_id,),
    ).fetchall()

    repaired_edges = 0

    try:
        connection.execute(
            "BEGIN IMMEDIATE"
        )

        # ----------------------------------------------------
        # Alias edge'lerini canonical edge kimliğine taşı.
        # raw_text değiştirilmez; kaynak typo'su provenance
        # olarak aynen saklanır.
        # ----------------------------------------------------

        for edge in alias_edges:
            canonical_edge_id = _stable_id(
                "edge",
                edge["source_version_id"],
                edge["source_clause_id"] or "",
                "3GPP",
                code_value,
                str(edge["ref_number"] or ""),
            )

            connection.execute(
                """
                INSERT INTO reference_edges(
                    id,
                    source_version_id,
                    source_clause_id,
                    target_document_id,
                    target_org,
                    target_code,
                    ref_number,
                    raw_text,
                    reference_kind
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)

                ON CONFLICT(id)
                DO UPDATE SET
                    target_document_id =
                        excluded.target_document_id,
                    target_org =
                        excluded.target_org,
                    target_code =
                        excluded.target_code,
                    ref_number =
                        excluded.ref_number,
                    raw_text =
                        excluded.raw_text,
                    reference_kind =
                        excluded.reference_kind
                """,
                (
                    canonical_edge_id,
                    edge["source_version_id"],
                    edge["source_clause_id"],
                    canonical_document_id,
                    "3GPP",
                    code_value,
                    edge["ref_number"],
                    edge["raw_text"],
                    edge["reference_kind"],
                ),
            )

            # Eski edge bir crawl job'ın discovery kaynağıysa
            # foreign key'i canonical edge'e geçir.
            if crawl_jobs_exists:
                connection.execute(
                    """
                    UPDATE crawl_jobs
                    SET discovered_from_edge_id = ?
                    WHERE discovered_from_edge_id = ?
                    """,
                    (
                        canonical_edge_id,
                        edge["id"],
                    ),
                )

            if canonical_edge_id != edge["id"]:
                connection.execute(
                    """
                    DELETE FROM reference_edges
                    WHERE id = ?
                    """,
                    (edge["id"],),
                )

            repaired_edges += 1

        # ----------------------------------------------------
        # Alias crawl job -> canonical crawl job
        # ----------------------------------------------------

        if crawl_jobs_exists:
            alias_job = connection.execute(
                """
                SELECT *
                FROM crawl_jobs
                WHERE document_id = ?
                """,
                (alias_document_id,),
            ).fetchone()

            canonical_job = connection.execute(
                """
                SELECT *
                FROM crawl_jobs
                WHERE document_id = ?
                """,
                (canonical_document_id,),
            ).fetchone()

            canonical_source_url = (
                canonical_version["source_url"]
                or ""
            )

            if alias_job is not None:
                if canonical_job is None:
                    connection.execute(
                        """
                        INSERT INTO crawl_jobs(
                            document_id,
                            depth,
                            status,
                            attempts,
                            discovered_from_edge_id,
                            source_url,
                            last_error,
                            updated_at
                        )
                        VALUES (
                            ?,
                            ?,
                            'indexed',
                            ?,
                            ?,
                            ?,
                            '',
                            CURRENT_TIMESTAMP
                        )
                        """,
                        (
                            canonical_document_id,
                            alias_job["depth"],
                            alias_job["attempts"],
                            alias_job[
                                "discovered_from_edge_id"
                            ],
                            canonical_source_url,
                        ),
                    )

                else:
                    alias_is_shallower = (
                        alias_job["depth"]
                        < canonical_job["depth"]
                    )

                    if alias_is_shallower:
                        discovered_from_edge_id = (
                            alias_job[
                                "discovered_from_edge_id"
                            ]
                        )
                    else:
                        discovered_from_edge_id = (
                            canonical_job[
                                "discovered_from_edge_id"
                            ]
                            or alias_job[
                                "discovered_from_edge_id"
                            ]
                        )

                    connection.execute(
                        """
                        UPDATE crawl_jobs
                        SET
                            depth = MIN(depth, ?),
                            status = 'indexed',
                            attempts = MAX(attempts, ?),
                            discovered_from_edge_id = ?,
                            source_url = ?,
                            last_error = '',
                            updated_at =
                                CURRENT_TIMESTAMP
                        WHERE document_id = ?
                        """,
                        (
                            alias_job["depth"],
                            alias_job["attempts"],
                            discovered_from_edge_id,
                            (
                                canonical_source_url
                                or canonical_job[
                                    "source_url"
                                ]
                                or alias_job[
                                    "source_url"
                                ]
                            ),
                            canonical_document_id,
                        ),
                    )

                connection.execute(
                    """
                    DELETE FROM crawl_jobs
                    WHERE document_id = ?
                    """,
                    (alias_document_id,),
                )

        # ----------------------------------------------------
        # Alias artık hiçbir yerde target olmamalı.
        # ----------------------------------------------------

        remaining_edges = connection.execute(
            """
            SELECT COUNT(*)
            FROM reference_edges
            WHERE target_document_id = ?
            """,
            (alias_document_id,),
        ).fetchone()[0]

        if remaining_edges != 0:
            raise RuntimeError(
                "3GPP alias repair sonrası "
                f"{remaining_edges} edge alias'a bağlı kaldı."
            )

        # Alias'ın version'ı olmadığını yukarıda doğruladık.
        connection.execute(
            """
            DELETE FROM documents
            WHERE id = ?
            """,
            (alias_document_id,),
        )

        connection.commit()

    except Exception:
        connection.rollback()
        raise

    return repaired_edges


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


def _prepare_ietf_document_text(
    document_text: str,
) -> str:
    """
    Modern RFC HTML metinlerinde madde numaras?
    ve ba?l?k ayr? sat?rlarda bulunabilir:

        1.
        Introduction

    Chunker'?n bekledi?i tek sat?rl? ba?l??a
    d?n??t?r?r:

        1. Introduction
    """

    lines = (
        document_text
        or ""
    ).splitlines()

    prepared_lines: list[str] = []
    index = 0

    section_number = re.compile(
        r"^\s*"
        r"(?P<number>"
        r"\d+(?:\.\d+)*"
        r")"
        r"\.\s*$"
    )

    while index < len(lines):
        current_line = lines[index]
        current_clean = (
            current_line.strip()
        )

        match = section_number.fullmatch(
            current_clean
        )

        if (
            match is not None
            and index + 1 < len(lines)
        ):
            title_line = (
                lines[index + 1]
                .strip()
            )

            title_is_usable = (
                bool(title_line)
                and title_line
                not in {
                    "?",
                    "?",
                }
                and len(title_line) <= 240
                and not re.fullmatch(
                    r"\d+(?:\.\d+)*\.?",
                    title_line,
                )
                and not title_line.startswith(
                    (
                        "http://",
                        "https://",
                    )
                )
            )

            if title_is_usable:
                prepared_lines.append(
                    f"{match.group('number')} "
                    f"{title_line}"
                )
                index += 2
                continue

        prepared_lines.append(
            current_line
        )
        index += 1

    return "\n".join(
        prepared_lines
    )


def _prepare_document_text(
    org: str,
    document_text: str,
) -> str:
    normalized_org = (
        org
        or ""
    ).strip().upper()

    if normalized_org == "IETF":
        return _prepare_ietf_document_text(
            document_text
        )

    if normalized_org != "ETSI":
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
    crawl_jobs_exists = (
        catalog.connection.execute(
            """
            SELECT 1
            FROM sqlite_master
            WHERE
                type = 'table'
                AND name = 'crawl_jobs'
            """
        ).fetchone()
        is not None
    )

    if crawl_jobs_exists:
        catalog.connection.execute(
            """
            UPDATE crawl_jobs
            SET discovered_from_edge_id = NULL
            WHERE discovered_from_edge_id IN (
                SELECT id
                FROM reference_edges
                WHERE source_version_id = ?
            )
            """,
            (version_id,),
        )

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
        (
            target_org,
            target_code,
        ) = _canonicalize_3gpp_reference(
            catalog,
            reference.org,
            reference.code,
        )

        target_document_id = (
            catalog.upsert_document(
                org=target_org,
                code=target_code,
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
            target_org=target_org,
            target_code=target_code,
            ref_number=(
                reference.ref_number
            ),
            raw_text=reference.raw_text,
            reference_kind=(
                reference.reference_kind
            ),
        )

    _repair_opposite_3gpp_alias(
        catalog,
        canonical_document_id=document_id,
        org=document.org,
        code=document.code,
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