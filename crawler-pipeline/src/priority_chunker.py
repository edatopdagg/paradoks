from __future__ import annotations

import re

from chunker import build_chunks


MIN_SEARCHABLE_CHARS = 30


def _normalize(
    value: str,
) -> str:
    return " ".join(
        (value or "").split()
    ).casefold()


def _strip_single_character_runs(
    text: str,
    *,
    min_run: int = 8,
) -> str:

    lines = (
        text or ""
    ).splitlines()

    output: list[str] = []

    index = 0

    while index < len(lines):

        current = (
            lines[index].strip()
        )

        if (
            current
            and len(current) <= 1
        ):

            start = index

            while index < len(lines):

                value = (
                    lines[index]
                    .strip()
                )

                if (
                    not value
                    or len(value) > 1
                ):
                    break

                index += 1

            run_length = (
                index - start
            )

            if (
                run_length
                < min_run
            ):
                output.extend(
                    lines[
                        start:index
                    ]
                )

            continue

        output.append(
            lines[index]
        )

        index += 1

    return "\n".join(
        output
    )


def _remove_toc_rows(
    text: str,
) -> str:
    """
    Örn:
        4.2 Architecture ............... 27
    gibi TOC satırlarını çıkarır.
    """

    output = []

    for line in (
        text or ""
    ).splitlines():

        stripped = (
            line.strip()
        )

        if not stripped:
            output.append("")
            continue

        if re.search(
            r"\.{5,}\s*\d+\s*$",
            stripped,
        ):
            continue

        output.append(
            line
        )

    return "\n".join(
        output
    )


def _remove_postal_address_lines(
    text: str,
) -> str:
    """
    Generic parser'ın:

        1200 G Street
        1919 S. Eads St.
        1771 N Street

    gibi adresleri section numarası
    sanmasını engeller.
    """

    address_pattern = re.compile(
        r"""
        ^\s*
        \d{3,5}
        \s+
        .*
        (?:
            street |
            st\.? |
            avenue |
            ave\.? |
            road |
            rd\.? |
            boulevard |
            blvd\.? |
            drive |
            dr\.? |
            lane |
            ln\.?
        )
        \b
        """,
        flags=(
            re.IGNORECASE
            | re.VERBOSE
        ),
    )

    output = []

    for line in (
        text or ""
    ).splitlines():

        if address_pattern.search(
            line.strip()
        ):
            continue

        output.append(
            line
        )

    return "\n".join(
        output
    )


def _trim_standard_front_matter(
    *,
    org: str,
    text: str,
) -> str:
    """
    ATIS ve ETSI gibi belgelerde
    copyright / address / contents
    bölümünü mümkünse gerçek
    Clause 1 Scope başlangıcından keser.
    """

    normalized_org = (
        org or ""
    ).strip().upper()

    if normalized_org not in {
        "ATIS",
        "ETSI",
    }:
        return text

    lines = text.splitlines()

    pattern = re.compile(
        r"""
        ^\s*
        1
        (?:\.0)?
        \s+
        scope
        (?:
            \s*$
            |
            [,&\s].*$
        )
        """,
        flags=(
            re.IGNORECASE
            | re.VERBOSE
        ),
    )

    candidates = []

    for index, line in enumerate(
        lines
    ):

        clean = (
            line.strip()
        )

        if pattern.match(
            clean
        ):
            candidates.append(
                index
            )

    if not candidates:
        return text

    return "\n".join(
        lines[
            candidates[0]:
        ]
    )


def prepare_priority_text(
    *,
    org: str,
    document_text: str,
) -> str:

    text = (
        document_text
        or ""
    )

    text = (
        _strip_single_character_runs(
            text
        )
    )

    text = (
        _remove_cid_tokens(
            text
        )
    )

    text = (
        _remove_postal_address_lines(
            text
        )
    )

    text = (
        _remove_toc_rows(
            text
        )
    )

    text = (
        _trim_standard_front_matter(
            org=org,
            text=text,
        )
    )

    return text


def _remove_cid_tokens(
    text: str,
) -> str:
    """
    PDF extraction sırasında kalan:

        (cid:123)

    biçimindeki karakter-map artıkları gerçek
    teknik içerik değildir.

    Tokenı kaldırır fakat chunk'ın geri kalan
    anlamlı metnini korur.
    """

    return re.sub(
        r"\(cid:\d+\)",
        " ",
        text or "",
        flags=re.IGNORECASE,
    )


def _cid_count(
    text: str,
) -> int:

    return len(
        re.findall(
            r"\(cid:\d+\)",
            text or "",
            flags=re.IGNORECASE,
        )
    )


def _low_value_chunk(
    *,
    text: str,
    title: str,
) -> bool:

    clean_text = (
        text or ""
    ).strip()

    clean_title = (
        title or ""
    ).strip()

    if not clean_text:
        return True

    # Heading-only.
    if (
        _normalize(
            clean_text
        )
        == _normalize(
            clean_title
        )
    ):
        return True

    # Retrieval açısından anlamsız
    # minicik parçalar.
    if len(clean_text) < (
        MIN_SEARCHABLE_CHARS
    ):
        return True

    # CID encoding garbage.
    if _cid_count(
        clean_text
    ) >= 3:
        return True

    # ETSI kapak metadata chunk'ları.
    normalized = (
        _normalize(
            clean_text
        )
    )

    if (
        normalized.startswith(
            "etsi "
        )
        and "reference" in normalized
        and "keywords" in normalized
        and len(clean_text) < 500
    ):
        return True

    return False


def searchable_chunks(
    chunks,
):
    output = []

    for chunk in chunks:

        text = (
            getattr(
                chunk,
                "text",
                "",
            )
            or ""
        ).strip()

        title = (
            getattr(
                chunk,
                "clause_title",
                "",
            )
            or ""
        ).strip()

        if _low_value_chunk(
            text=text,
            title=title,
        ):
            continue

        output.append(
            chunk
        )

    return output


def _page_fallback_text(
    *,
    page_texts: tuple[
        str,
        ...
    ],
    doc_org: str,
) -> str:

    parts = []

    for page_number, page_text in enumerate(
        page_texts,
        start=1,
    ):

        clean = (
            prepare_priority_text(
                org=doc_org,
                document_text=(
                    page_text
                    or ""
                ),
            )
            .strip()
        )

        if len(clean) < (
            MIN_SEARCHABLE_CHARS
        ):
            continue

        if _cid_count(
            clean
        ) >= 5:
            continue

        parts.append(
            (
                f"{page_number} "
                f"Page {page_number}\n"
                f"{clean}"
            )
        )

    return "\n\n".join(
        parts
    )


def build_priority_chunks(
    *,
    document_text: str,
    page_texts: tuple[
        str,
        ...
    ],
    doc_org: str,
    doc_code: str,
    version: str,
    source_url: str | None = None,
):

    prepared = (
        prepare_priority_text(
            org=doc_org,
            document_text=document_text,
        )
    )

    normal_chunks = build_chunks(
        document_text=prepared,
        doc_org=doc_org,
        doc_code=doc_code,
        version=version,
        source_url=source_url,
    )

    normal_searchable = (
        searchable_chunks(
            normal_chunks
        )
    )

    clauses = {
        (
            getattr(
                chunk,
                "clause",
                "",
            )
            or ""
        ).strip()
        for chunk in normal_searchable
        if (
            getattr(
                chunk,
                "clause",
                "",
            )
            or ""
        ).strip()
    }

    reason = ""

    if not normal_searchable:

        reason = (
            "zero_searchable_chunks"
        )

    elif (
        len(prepared) >= 50000
        and len(clauses) <= 1
    ):

        reason = (
            "large_document_single_clause"
        )

    elif (
        doc_org.strip().upper()
        == "ATIS"
        and "1200" in clauses
    ):

        reason = (
            "atis_address_clause"
        )

    elif (
        sum(
            _cid_count(
                getattr(
                    chunk,
                    "text",
                    "",
                )
                or ""
            )
            for chunk
            in normal_searchable
        )
        > 20
    ):

        reason = (
            "cid_garbage"
        )

    if not reason:

        return {
            "strategy": (
                "production"
            ),
            "reason": "",
            "chunks": (
                normal_searchable
            ),
        }

    fallback_text = (
        _page_fallback_text(
            page_texts=page_texts,
            doc_org=doc_org,
        )
    )

    if not fallback_text.strip():

        return {
            "strategy": (
                "failed"
            ),
            "reason": (
                reason
                + ":empty_fallback"
            ),
            "chunks": [],
        }

    fallback_chunks = build_chunks(
        document_text=fallback_text,
        doc_org=doc_org,
        doc_code=doc_code,
        version=version,
        source_url=source_url,
    )

    fallback_searchable = (
        searchable_chunks(
            fallback_chunks
        )
    )

    return {
        "strategy": (
            "page_fallback"
        ),
        "reason": reason,
        "chunks": (
            fallback_searchable
        ),
    }
