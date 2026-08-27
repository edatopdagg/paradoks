"""
Telekom standartlarını clause/section bazında chunk'lara ayırır.

Desteklenen temel organizasyonlar:

- 3GPP
- IETF
- Generic fallback

3GPP ve IETF dokümanları farklı bölüm yapılarına sahip
olduğundan organizasyona özel parser kullanılır.

Hem 3GPP hem IETF tarafında mümkün olduğunda
Table of Contents (TOC) whitelist olarak kullanılır.

Bu sayede doküman gövdesindeki:

    1 Introduction
    2 Example
    3 Procedure

gibi yerel numaralandırmaların yanlışlıkla gerçek
clause/section olarak kabul edilmesi azaltılır.

3GPP tarafında extraction sırasında clause numarası
kısmen veya tamamen kaybolursa TOC kullanılarak
kontrollü recovery uygulanır.

Desteklenen recovery örnekleri:

    GPRS attach procedures
        ->
    4.1.1 GPRS attach procedures

ve:

    .2 Successful GPRS attach procedures
        ->
    4.1.1.2 Successful GPRS attach procedures

ve extraction sırasında başlığın bazı karakterleri
kaybolmuşsa:

    ttached subscribers
        ->
    Attached subscribers

    DP context activation procedures
        ->
    PDP context activation procedures

    -TMSI reallocation procedures
        ->
    P-TMSI reallocation procedures

Clause numarası sağlam kalıp başlığın bazı kelimeleri
kaybolmuşsa da kontrollü recovery uygulanır.

Örnek:

    A.6.1.3.1.4 Heterogeneous Configurations
        ->
    A.6.1.3.1.4 Heterogeneous TDM Port Configurations

Recovery yalnızca TOC içerisinde güvenli bir
eşleşme bulunduğunda uygulanır.

Exact recovery ve fuzzy/damaged recovery yalnızca
TOC'da sıradaki beklenen clause için uygulanır.

Exact clause number + damaged title recovery de
yalnızca TOC'da sıradaki beklenen clause için
uygulanır.

Böylece gövde içindeki:

    Introduction
    General
    Evaluation
    Option 1:

gibi normal metinlerin parser'ı ilerideki clause'lara
yanlışlıkla atlatması engellenir.
"""

import re

from difflib import SequenceMatcher

from models import Chunk, DocStatus


# =========================================================
# CHUNK AYARLARI
# =========================================================

MAX_CHUNK_CHARS = 2400
CHUNK_OVERLAP_CHARS = 300


# =========================================================
# GENERIC NUMERIC CLAUSE
# =========================================================

GENERIC_CLAUSE_HEADING = re.compile(
    r"^(\d+(?:\.\d+)*)[ \t]+(.+)$"
)


# =========================================================
# 3GPP CLAUSE TOKEN
#
# Örnek:
#
# 0
# 0a
# 1
# 1.1
# 9.1.3.4.2
# A
# A.1
# A.1.3
# =========================================================

GPP_CLAUSE_TOKEN_PATTERN = (
    r"(?:"
    r"\d+[A-Za-z]?(?:\.\d+)*"
    r"|"
    r"[A-Z](?:\.\d+)*"
    r")"
)


# =========================================================
# 3GPP TEK SATIR HEADING
# =========================================================

GPP_SECTION_HEADING = re.compile(
    rf"^\s*"
    rf"({GPP_CLAUSE_TOKEN_PATTERN})"
    rf"\.?"
    rf"[ \t]+"
    rf"(.+?)"
    rf"\s*$",
    re.IGNORECASE,
)


# =========================================================
# 3GPP RECOVERY - SUFFIX HEADING
#
# .1 Title
# .2 Title
# .1.2 Title
# =========================================================

GPP_SUFFIX_HEADING = re.compile(
    r"^\s*"
    r"(\.\d+(?:\.\d+)*)"
    r"[ \t]+"
    r"(.+?)"
    r"\s*$"
)


# =========================================================
# 3GPP ANNEX ANA BAŞLIĞI
# =========================================================

GPP_ANNEX_HEADING = re.compile(
    r"^\s*"
    r"Annex[ \t]+"
    r"([A-Z]|\d+)"
    r"(?:[ \t]*\([^)]*\))?"
    r"[ \t]*:?"
    r"[ \t]*(.*?)"
    r"\s*$",
    re.IGNORECASE,
)


# =========================================================
# 3GPP TOC ENTRY
# =========================================================

GPP_TOC_ENTRY = re.compile(
    rf"^\s*"
    rf"({GPP_CLAUSE_TOKEN_PATTERN})"
    rf"\.?"
    rf"[ \t]+"
    rf"(.+?)"
    rf"[ \t]+"
    rf"(\d+)"
    rf"\s*$",
    re.IGNORECASE,
)


# =========================================================
# 3GPP ANNEX TOC ENTRY
# =========================================================

GPP_ANNEX_TOC_ENTRY = re.compile(
    r"^\s*"
    r"Annex[ \t]+"
    r"([A-Z]|\d+)"
    r"(?:[ \t]*\([^)]*\))?"
    r"[ \t]*:?"
    r"[ \t]*(.*?)"
    r"[ \t]+"
    r"(\d+)"
    r"\s*$",
    re.IGNORECASE,
)


# =========================================================
# IETF HEADING
# =========================================================

IETF_SECTION_HEADING = re.compile(
    r"^([1-9]\d?(?:\.\d+)*)\.?[ \t]+(.+)$"
)


IETF_SECTION_NUMBER = re.compile(
    r"^([1-9]\d?(?:\.\d+)*)\.?$"
)


# =========================================================
# IETF TOC
# =========================================================

RFC_TOC_SINGLE_LINE = re.compile(
    r"^\s*"
    r"([1-9]\d?(?:\.\d+)*)"
    r"\.?"
    r"\s+"
    r"(.+?)"
    r"(?:"
    r"\s+\.{2,}\s*"
    r"|"
    r"\s{2,}"
    r")"
    r"(\d+)"
    r"\s*$"
)


RFC_TOC_LINE = re.compile(
    r"^\s*"
    r"\d+(?:\.\d+)*"
    r"\.?"
    r"\s+"
    r".+?"
    r"\s+"
    r"(?:\.{2,}\s*)?"
    r"\d{1,4}"
    r"\s*$"
)


RFC_PAGE_NUMBER = re.compile(
    r"^\d{1,4}$"
)


# =========================================================
# GENEL YARDIMCILAR
# =========================================================

def _normalize_whitespace(
    text: str,
) -> str:

    return re.sub(
        r"\s+",
        " ",
        text or "",
    ).strip()


def _clean_title(
    text: str,
) -> str:

    value = (
        text or ""
    ).strip()

    value = re.sub(
        r"\s+",
        " ",
        value,
    )

    return value.strip()


def _clean_3gpp_title(
    text: str,
) -> str:

    value = _clean_title(
        text
    )

    value = value.rstrip(
        " \t.:"
    )

    return _normalize_whitespace(
        value
    )


def _3gpp_titles_match(
    left: str,
    right: str,
) -> bool:

    return (
        _clean_3gpp_title(
            left
        ).casefold()
        ==
        _clean_3gpp_title(
            right
        ).casefold()
    )


def _clean_rfc_title(
    text: str,
) -> str:

    value = (
        text or ""
    ).strip()

    value = re.sub(
        r"^\.\s*",
        "",
        value,
    )

    value = re.sub(
        r"\s*(?:\.\s*){2,}$",
        "",
        value,
    )

    return _normalize_whitespace(
        value
    )


def _titles_match(
    left: str,
    right: str,
) -> bool:

    return (
        _clean_rfc_title(
            left
        ).casefold()
        ==
        _clean_rfc_title(
            right
        ).casefold()
    )


def _looks_like_rfc_toc_title(
    title: str,
) -> bool:

    cleaned = _clean_rfc_title(
        title
    )

    if not cleaned:
        return False

    if re.fullmatch(
        r"\d+(?:\.\d+)*\.?",
        cleaned,
    ):
        return False

    if not re.search(
        r"[A-Za-z]",
        cleaned,
    ):
        return False

    return True


# =========================================================
# 3GPP TABLE OF CONTENTS
# =========================================================

def _find_3gpp_toc_start(
    lines: list[str],
) -> int | None:

    for index, line in enumerate(
        lines
    ):

        normalized = (
            line
            .strip()
            .casefold()
        )

        if normalized in {
            "contents",
            "table of contents",
        }:

            return index

    return None


def _parse_3gpp_toc_entry(
    line: str,
) -> tuple[str, str] | None:

    candidate = (
        line or ""
    ).strip()

    if not candidate:
        return None

    # -------------------------------------------------
    # ANNEX TOC
    # -------------------------------------------------

    annex_match = (
        GPP_ANNEX_TOC_ENTRY.fullmatch(
            candidate
        )
    )

    if annex_match:

        annex_id = (
            annex_match
            .group(1)
            .upper()
        )

        raw_title = (
            annex_match
            .group(2)
            .strip()
        )

        if annex_id.isdigit():

            clause_number = (
                f"ANNEX-{annex_id}"
            )

        else:

            clause_number = (
                annex_id
            )

        title = (
            _clean_3gpp_title(
                raw_title
            )
        )

        if not title:

            title = (
                f"Annex {annex_id}"
            )

        return (
            clause_number,
            title,
        )

    # -------------------------------------------------
    # NORMAL TOC
    # -------------------------------------------------

    normal_match = (
        GPP_TOC_ENTRY.fullmatch(
            candidate
        )
    )

    if not normal_match:
        return None

    clause_number = (
        normal_match
        .group(1)
        .rstrip(".")
    )

    title = (
        _clean_3gpp_title(
            normal_match
            .group(2)
        )
    )

    if not title:
        return None

    # "650 Route des Lucioles ..." gibi
    # adres satırlarını engelle.
    if (
        clause_number.isdigit()
        and "." not in clause_number
    ):

        try:

            if int(
                clause_number
            ) > 99:

                return None

        except ValueError:

            return None

    return (
        clause_number.upper(),
        title,
    )


def _extract_3gpp_toc(
    lines: list[str],
) -> tuple[
    dict[str, str],
    int | None,
    int | None,
]:

    toc_start = (
        _find_3gpp_toc_start(
            lines
        )
    )

    if toc_start is None:

        return (
            {},
            None,
            None,
        )

    sections: dict[
        str,
        str,
    ] = {}

    toc_end = toc_start

    scan_end = min(
        len(lines),
        toc_start + 1500,
    )

    i = toc_start + 1

    gap_count = 0
    toc_started = False

    while i < scan_end:

        parsed = (
            _parse_3gpp_toc_entry(
                lines[i]
            )
        )

        if parsed is not None:

            (
                clause_number,
                clause_title,
            ) = parsed

            if (
                clause_number
                not in sections
            ):

                sections[
                    clause_number
                ] = clause_title

            toc_end = i

            toc_started = True
            gap_count = 0

            i += 1
            continue

        if toc_started:

            gap_count += 1

            if gap_count > 6:
                break

        i += 1

    return (
        sections,
        toc_start,
        toc_end,
    )


# =========================================================
# 3GPP TOC POZİSYONLARI
# =========================================================

def _build_3gpp_toc_positions(
    toc_sections: dict[str, str],
) -> dict[str, int]:

    return {
        clause_number: index
        for index, clause_number
        in enumerate(
            toc_sections.keys()
        )
    }


# =========================================================
# 3GPP SIRADAKİ BEKLENEN CLAUSE
# =========================================================

def _get_next_3gpp_toc_clause(
    toc_sections: dict[str, str],
    toc_positions: dict[str, int],
    seen_sections: set[str],
    last_toc_position: int,
) -> tuple[
    str,
    str,
    int,
] | None:

    target_position = (
        last_toc_position + 1
    )

    for (
        clause_number,
        clause_title,
    ) in toc_sections.items():

        position = (
            toc_positions.get(
                clause_number,
                -1,
            )
        )

        if (
            position
            != target_position
        ):
            continue

        if (
            clause_number
            in seen_sections
        ):
            continue

        return (
            clause_number,
            clause_title,
            position,
        )

    return None


# =========================================================
# 3GPP GERÇEK HEADING MATCH
# =========================================================

def _match_3gpp_heading_against_toc(
    line: str,
    toc_sections: dict[str, str],
) -> tuple[str, str] | None:

    if not line:
        return None

    candidate = (
        line.strip()
    )

    if not candidate:
        return None

    # -------------------------------------------------
    # ANNEX
    # -------------------------------------------------

    annex_match = (
        GPP_ANNEX_HEADING.fullmatch(
            candidate
        )
    )

    if annex_match:

        annex_id = (
            annex_match
            .group(1)
            .upper()
        )

        if annex_id.isdigit():

            clause_number = (
                f"ANNEX-{annex_id}"
            )

        else:

            clause_number = (
                annex_id
            )

        expected_title = (
            toc_sections.get(
                clause_number
            )
        )

        if expected_title is None:
            return None

        return (
            clause_number,
            expected_title,
        )

    # -------------------------------------------------
    # NORMAL
    # -------------------------------------------------

    heading_match = (
        GPP_SECTION_HEADING.fullmatch(
            candidate
        )
    )

    if not heading_match:
        return None

    clause_number = (
        heading_match
        .group(1)
        .rstrip(".")
        .upper()
    )

    title = (
        _clean_3gpp_title(
            heading_match
            .group(2)
        )
    )

    expected_title = (
        toc_sections.get(
            clause_number
        )
    )

    if expected_title is None:
        return None

    if not _3gpp_titles_match(
        title,
        expected_title,
    ):

        return None

    return (
        clause_number,
        expected_title,
    )


# =========================================================
# 3GPP EXACT RECOVERY
# =========================================================

def _match_3gpp_recovered_heading(
    line: str,
    toc_sections: dict[str, str],
    seen_sections: set[str],
    toc_positions: dict[str, int],
    last_toc_position: int,
) -> tuple[
    str,
    str,
    str,
] | None:

    candidate = (
        line or ""
    ).strip()

    if not candidate:
        return None

    # -------------------------------------------------
    # BODY SATIRLARINI ELE
    # -------------------------------------------------

    if re.match(
        r"^[a-zA-Z]\)",
        candidate,
    ):
        return None

    if re.match(
        r"^(NOTE|Figure|Table)\b",
        candidate,
        re.IGNORECASE,
    ):
        return None

    if re.match(
        r"^-\s+",
        candidate,
    ):
        return None

    if candidate.startswith(
        (
            "•",
            "[",
        )
    ):
        return None

    if len(candidate) > 300:
        return None

    # -------------------------------------------------
    # YALNIZCA SIRADAKİ BEKLENEN TOC CLAUSE
    # -------------------------------------------------

    next_clause = (
        _get_next_3gpp_toc_clause(
            toc_sections=toc_sections,
            toc_positions=toc_positions,
            seen_sections=seen_sections,
            last_toc_position=last_toc_position,
        )
    )

    if next_clause is None:
        return None

    (
        expected_clause_number,
        expected_title,
        _expected_position,
    ) = next_clause

    # =================================================
    # 1. SUFFIX NUMBER RECOVERY
    # =================================================

    suffix_match = (
        GPP_SUFFIX_HEADING.fullmatch(
            candidate
        )
    )

    if suffix_match:

        suffix = (
            suffix_match
            .group(1)
            .strip()
        )

        candidate_title = (
            _clean_3gpp_title(
                suffix_match
                .group(2)
            )
        )

        if not (
            expected_clause_number
            .upper()
            .endswith(
                suffix.upper()
            )
        ):
            return None

        if not _3gpp_titles_match(
            candidate_title,
            expected_title,
        ):
            return None

        return (
            expected_clause_number,
            expected_title,
            "suffix_number",
        )

    # =================================================
    # 2. TITLE ONLY RECOVERY
    # =================================================

    candidate_title = (
        _clean_3gpp_title(
            candidate
        )
    )

    if not candidate_title:
        return None

    if not _3gpp_titles_match(
        candidate_title,
        expected_title,
    ):
        return None

    return (
        expected_clause_number,
        expected_title,
        "title_only",
    )


# =========================================================
# 3GPP FUZZY TITLE NORMALIZATION
# =========================================================

def _normalize_3gpp_fuzzy_title(
    text: str,
) -> str:

    value = (
        text or ""
    ).strip()

    value = re.sub(
        r"^\.\d+(?:\.\d+)*\s+",
        "",
        value,
    )

    value = (
        _clean_3gpp_title(
            value
        )
        .casefold()
    )

    value = (
        value
        .replace("–", "-")
        .replace("—", "-")
    )

    value = re.sub(
        r"[^\w\s\-'/()]+",
        " ",
        value,
    )

    value = re.sub(
        r"\s+",
        " ",
        value,
    ).strip()

    return value


# =========================================================
# 3GPP FUZZY SCORE
# =========================================================

def _3gpp_fuzzy_title_score(
    candidate: str,
    expected: str,
) -> float:

    left = (
        _normalize_3gpp_fuzzy_title(
            candidate
        )
    )

    right = (
        _normalize_3gpp_fuzzy_title(
            expected
        )
    )

    if not left or not right:
        return 0.0

    sequence_score = (
        SequenceMatcher(
            None,
            left,
            right,
        ).ratio()
    )

    left_words = set(
        left.split()
    )

    right_words = set(
        right.split()
    )

    if (
        left_words
        and right_words
    ):

        word_score = (
            len(
                left_words
                & right_words
            )
            /
            max(
                len(left_words),
                len(right_words),
            )
        )

    else:

        word_score = 0.0

    return (
        sequence_score * 0.75
        +
        word_score * 0.25
    )


# =========================================================
# 3GPP EXACT NUMBER + DAMAGED TITLE RECOVERY
# =========================================================

def _match_3gpp_exact_number_damaged_title(
    line: str,
    toc_sections: dict[str, str],
    seen_sections: set[str],
    toc_positions: dict[str, int],
    last_toc_position: int,
) -> tuple[
    str,
    str,
    str,
] | None:
    """
    Clause numarası sağlam ancak başlığın bazı
    karakterleri veya kelimeleri extraction sırasında
    kaybolmuşsa recovery yapar.

    Örnek:

        A.6.1.3.1.4 Heterogeneous Configurations

    TOC:

        A.6.1.3.1.4 Heterogeneous TDM Port Configurations

    Güvenlik:

    - clause numarası satırda açıkça bulunmalıdır
    - clause TOC'da bulunmalıdır
    - daha önce parse edilmemiş olmalıdır
    - TOC'da TAM OLARAK sıradaki beklenen clause olmalıdır
    - title fuzzy skoru minimum eşiği geçmelidir

    Bu nedenle parser uzak bir TOC pozisyonuna
    sıçrayamaz.
    """

    candidate = (
        line or ""
    ).strip()

    if not candidate:
        return None

    if len(candidate) > 300:
        return None

    # -------------------------------------------------
    # NUMARALI HEADING OLMALI
    # -------------------------------------------------

    heading_match = (
        GPP_SECTION_HEADING.fullmatch(
            candidate
        )
    )

    if not heading_match:
        return None

    clause_number = (
        heading_match
        .group(1)
        .rstrip(".")
        .upper()
    )

    candidate_title = (
        _clean_3gpp_title(
            heading_match
            .group(2)
        )
    )

    if not candidate_title:
        return None

    # -------------------------------------------------
    # TOC'DA OLMALI
    # -------------------------------------------------

    expected_title = (
        toc_sections.get(
            clause_number
        )
    )

    if expected_title is None:
        return None

    # -------------------------------------------------
    # DAHA ÖNCE GÖRÜLMEMİŞ OLMALI
    # -------------------------------------------------

    if (
        clause_number
        in seen_sections
    ):
        return None

    position = (
        toc_positions.get(
            clause_number,
            -1,
        )
    )

    # -------------------------------------------------
    # YALNIZCA SIRADAKİ BEKLENEN CLAUSE
    # -------------------------------------------------

    if (
        position
        != last_toc_position + 1
    ):
        return None

    # -------------------------------------------------
    # EXACT TITLE İSE ZATEN NORMAL MATCHER YAKALAR
    # -------------------------------------------------

    if _3gpp_titles_match(
        candidate_title,
        expected_title,
    ):
        return None

    # -------------------------------------------------
    # BODY BENZERİ SATIRLARA KARŞI TEMEL KORUMA
    # -------------------------------------------------

    if re.match(
        r"^(NOTE|Figure|Table)\b",
        candidate_title,
        re.IGNORECASE,
    ):
        return None

    if candidate_title.startswith(
        (
            "•",
            "[",
        )
    ):
        return None

    # -------------------------------------------------
    # FUZZY SCORE
    # -------------------------------------------------

    score = (
        _3gpp_fuzzy_title_score(
            candidate_title,
            expected_title,
        )
    )

    # Clause numarası birebir doğru,
    # TOC clause'u birebir doğru
    # ve pozisyon tam sıradaki clause olduğu için
    # generic damaged recovery'den daha düşük
    # threshold güvenli şekilde kullanılabilir.
    if score < 0.60:
        return None

    return (
        clause_number,
        expected_title,
        "exact_number_damaged_title",
    )


# =========================================================
# 3GPP DAMAGED/FUZZY RECOVERY
# =========================================================

def _match_3gpp_damaged_heading(
    line: str,
    toc_sections: dict[str, str],
    seen_sections: set[str],
    toc_positions: dict[str, int],
    last_toc_position: int,
) -> tuple[
    str,
    str,
    str,
] | None:

    candidate = (
        line or ""
    ).strip()

    if not candidate:
        return None

    # -------------------------------------------------
    # BODY SATIRLARINI ELE
    # -------------------------------------------------

    if re.match(
        r"^[a-zA-Z]\)",
        candidate,
    ):
        return None

    if re.match(
        r"^(NOTE|Figure|Table)\b",
        candidate,
        re.IGNORECASE,
    ):
        return None

    # "-TMSI..." extraction hasarı olabileceği için
    # yalnızca "- " şeklindeki bullet engellenir.
    if re.match(
        r"^-\s+",
        candidate,
    ):
        return None

    if candidate.startswith(
        (
            "•",
            "[",
        )
    ):
        return None

    if len(candidate) > 300:
        return None

    # -------------------------------------------------
    # SUFFIX
    # -------------------------------------------------

    suffix = None
    candidate_title = candidate

    suffix_match = (
        GPP_SUFFIX_HEADING.fullmatch(
            candidate
        )
    )

    if suffix_match:

        suffix = (
            suffix_match
            .group(1)
        )

        candidate_title = (
            suffix_match
            .group(2)
        )

    # -------------------------------------------------
    # YALNIZCA SIRADAKİ TOC CLAUSE
    # -------------------------------------------------

    next_clause = (
        _get_next_3gpp_toc_clause(
            toc_sections=toc_sections,
            toc_positions=toc_positions,
            seen_sections=seen_sections,
            last_toc_position=last_toc_position,
        )
    )

    if next_clause is None:
        return None

    (
        clause_number,
        expected_title,
        _toc_position,
    ) = next_clause

    # -------------------------------------------------
    # SUFFIX UYUMU
    # -------------------------------------------------

    if suffix is not None:

        if not (
            clause_number
            .upper()
            .endswith(
                suffix.upper()
            )
        ):
            return None

    # -------------------------------------------------
    # SCORE
    # -------------------------------------------------

    score = (
        _3gpp_fuzzy_title_score(
            candidate_title,
            expected_title,
        )
    )

    if score < 0.84:
        return None

    return (
        clause_number,
        expected_title,
        (
            "damaged_suffix"
            if suffix is not None
            else "damaged_title"
        ),
    )


# =========================================================
# 3GPP İÇERİK BAŞLANGICI
# =========================================================

def _find_3gpp_content_start(
    lines: list[str],
    toc_sections: dict[str, str],
    toc_end: int | None,
) -> int | None:

    if not toc_sections:
        return None

    search_start = (
        (
            toc_end + 1
        )
        if toc_end is not None
        else 0
    )

    first_sections = list(
        toc_sections.keys()
    )[:20]

    first_section_set = set(
        first_sections
    )

    for index in range(
        search_start,
        len(lines),
    ):

        heading = (
            _match_3gpp_heading_against_toc(
                line=lines[index],
                toc_sections=toc_sections,
            )
        )

        if heading is None:
            continue

        if (
            heading[0]
            in first_section_set
        ):

            return index

    return None


# =========================================================
# 3GPP FALLBACK
# =========================================================

def _match_3gpp_annex_without_toc(
    line: str,
) -> tuple[str, str] | None:

    candidate = (
        line or ""
    ).strip()

    if not candidate:
        return None

    match = re.fullmatch(
        r"([A-Z](?:\.\d+)+)"
        r"[ \t]+"
        r"(.+)",
        candidate,
        re.IGNORECASE,
    )

    if not match:
        return None

    return (
        match.group(1).upper(),
        _clean_3gpp_title(
            match.group(2)
        ),
    )


def _split_3gpp_without_toc(
    lines: list[str],
) -> list[
    tuple[str, str, str]
]:

    clauses = []

    current = None

    for line in lines:

        heading = (
            _match_3gpp_annex_without_toc(
                line
            )
        )

        if heading is not None:

            if current:

                clauses.append(
                    current
                )

            current = [
                heading[0],
                heading[1],
                [],
            ]

        elif current:

            current[2].append(
                line
            )

    if current:

        clauses.append(
            current
        )

    return [
        (
            clause_no,
            clause_title,
            "\n".join(
                body
            ).strip(),
        )
        for (
            clause_no,
            clause_title,
            body,
        ) in clauses
    ]


# =========================================================
# 3GPP SPLITTER
# =========================================================

def _split_3gpp_clauses(
    document_text: str,
) -> list[
    tuple[str, str, str]
]:

    if not document_text:
        return []

    lines = (
        document_text.splitlines()
    )

    (
        toc_sections,
        _toc_start,
        toc_end,
    ) = (
        _extract_3gpp_toc(
            lines
        )
    )

    # -------------------------------------------------
    # TOC YOK
    # -------------------------------------------------

    if not toc_sections:

        return (
            _split_3gpp_without_toc(
                lines
            )
        )

    toc_positions = (
        _build_3gpp_toc_positions(
            toc_sections
        )
    )

    content_start = (
        _find_3gpp_content_start(
            lines=lines,
            toc_sections=toc_sections,
            toc_end=toc_end,
        )
    )

    if content_start is None:

        content_start = (
            toc_end + 1
            if toc_end is not None
            else 0
        )

    clauses = []

    current_clause_no = None
    current_clause_title = None
    current_body = []

    seen_sections: set[str] = set()

    last_toc_position = -1

    # -------------------------------------------------
    # CLAUSE KAPAT
    # -------------------------------------------------

    def flush_current():

        nonlocal current_clause_no
        nonlocal current_clause_title
        nonlocal current_body

        if current_clause_no is None:
            return

        clauses.append(
            (
                current_clause_no,
                (
                    current_clause_title
                    or ""
                ),
                "\n".join(
                    current_body
                ).strip(),
            )
        )

        current_clause_no = None
        current_clause_title = None
        current_body = []

    # -------------------------------------------------
    # CLAUSE AÇ
    # -------------------------------------------------

    def open_clause(
        clause_number: str,
        clause_title: str,
    ):

        nonlocal current_clause_no
        nonlocal current_clause_title
        nonlocal current_body
        nonlocal last_toc_position

        flush_current()

        current_clause_no = (
            clause_number
        )

        current_clause_title = (
            clause_title
        )

        current_body = []

        seen_sections.add(
            clause_number
        )

        position = (
            toc_positions.get(
                clause_number
            )
        )

        if position is not None:

            last_toc_position = max(
                last_toc_position,
                position,
            )

    # -------------------------------------------------
    # TARAMA
    # -------------------------------------------------

    i = content_start

    while i < len(lines):

        line = (
            lines[i]
        )

        # =================================================
        # 1. EXACT
        # =================================================

        exact_heading = (
            _match_3gpp_heading_against_toc(
                line=line,
                toc_sections=toc_sections,
            )
        )

        if exact_heading is not None:

            (
                clause_number,
                clause_title,
            ) = exact_heading

            if (
                clause_number
                not in seen_sections
            ):

                position = (
                    toc_positions.get(
                        clause_number,
                        -1,
                    )
                )

                if (
                    position
                    > last_toc_position
                ):

                    open_clause(
                        clause_number,
                        clause_title,
                    )

                    i += 1
                    continue

        # =================================================
        # 2. EXACT NUMBER + DAMAGED TITLE
        # =================================================

        exact_number_damaged = (
            _match_3gpp_exact_number_damaged_title(
                line=line,
                toc_sections=toc_sections,
                seen_sections=seen_sections,
                toc_positions=toc_positions,
                last_toc_position=last_toc_position,
            )
        )

        if exact_number_damaged is not None:

            (
                clause_number,
                clause_title,
                _recovery_type,
            ) = exact_number_damaged

            open_clause(
                clause_number,
                clause_title,
            )

            i += 1
            continue

        # =================================================
        # 3. EXACT RECOVERY
        # =================================================

        recovered = (
            _match_3gpp_recovered_heading(
                line=line,
                toc_sections=toc_sections,
                seen_sections=seen_sections,
                toc_positions=toc_positions,
                last_toc_position=last_toc_position,
            )
        )

        if recovered is not None:

            (
                clause_number,
                clause_title,
                _recovery_type,
            ) = recovered

            position = (
                toc_positions.get(
                    clause_number,
                    -1,
                )
            )

            if (
                position
                > last_toc_position
            ):

                open_clause(
                    clause_number,
                    clause_title,
                )

                i += 1
                continue

        # =================================================
        # 4. DAMAGED / FUZZY RECOVERY
        # =================================================

        damaged = (
            _match_3gpp_damaged_heading(
                line=line,
                toc_sections=toc_sections,
                seen_sections=seen_sections,
                toc_positions=toc_positions,
                last_toc_position=last_toc_position,
            )
        )

        if damaged is not None:

            (
                clause_number,
                clause_title,
                _recovery_type,
            ) = damaged

            open_clause(
                clause_number,
                clause_title,
            )

            i += 1
            continue

        # =================================================
        # BODY
        # =================================================

        if (
            current_clause_no
            is not None
        ):

            current_body.append(
                line
            )

        i += 1

    flush_current()

    return clauses


# =========================================================
# IETF TABLE OF CONTENTS
# =========================================================

def _find_ietf_toc_start(
    lines: list[str],
) -> int | None:

    for index, line in enumerate(
        lines
    ):

        normalized = (
            line
            .strip()
            .casefold()
        )

        if normalized in (
            "table of contents",
            "contents",
        ):

            return index

    return None


def _extract_ietf_toc(
    lines: list[str],
) -> tuple[
    dict[str, str],
    int | None,
    int | None,
]:

    toc_start = (
        _find_ietf_toc_start(
            lines
        )
    )

    if toc_start is None:

        return (
            {},
            None,
            None,
        )

    sections = {}

    toc_end = (
        toc_start
    )

    scan_end = min(
        len(lines),
        toc_start + 3000,
    )

    i = (
        toc_start + 1
    )

    last_match_index = (
        toc_start
    )

    while i < scan_end:

        stripped = (
            lines[i].strip()
        )

        if not stripped:

            i += 1
            continue

        # -------------------------------------------------
        # GERÇEK İÇERİK BAŞLADI MI?
        # -------------------------------------------------
        # TOC'da daha önce gördüğümüz bir section numarası,
        # aynı başlıkla tekrar geliyorsa artık TOC değil,
        # dokümanın gerçek içeriğindeyiz.
        repeated_section = (
            IETF_SECTION_NUMBER.fullmatch(
                stripped
            )
        )

        if (
            sections
            and repeated_section
            and i + 1 < len(lines)
        ):
            section_number = (
                repeated_section.group(1)
            )

            expected_title = (
                sections.get(
                    section_number
                )
            )

            if expected_title is not None:
                actual_title = (
                    _clean_rfc_title(
                        re.sub(
                            r"^\s*\.\s*",
                            "",
                            lines[i + 1],
                        )
                    )
                )

                if _titles_match(
                    actual_title,
                    expected_title,
                ):
                    break

        # -------------------------------------------------
        # TEK SATIR TOC
        # -------------------------------------------------

        single_match = (
            RFC_TOC_SINGLE_LINE.fullmatch(
                stripped
            )
        )

        if single_match:

            section_number = (
                single_match
                .group(1)
                .strip()
            )

            raw_title = (
                single_match
                .group(2)
                .strip()
            )

            title = (
                _clean_rfc_title(
                    raw_title
                )
            )

            if (
                section_number
                and _looks_like_rfc_toc_title(
                    title
                )
            ):

                if (
                    section_number
                    not in sections
                ):

                    sections[
                        section_number
                    ] = title

                toc_end = i
                last_match_index = i

                i += 1
                continue

        # -------------------------------------------------
        # MODERN RFC: 3 SATIRLI TOC
        # örnek:
        # 1
        # .Â Â
        # Overview
        # -------------------------------------------------

        modern_section_match = (
            IETF_SECTION_NUMBER.fullmatch(
                stripped
            )
        )

        if (
            modern_section_match
            and i + 2 < scan_end
        ):
            separator_line = (
                lines[i + 1]
                .strip()
            )

            title_line = (
                lines[i + 2]
                .strip()
            )

            separator_normalized = (
                separator_line
                .replace("Â", "")
                .replace("\xa0", "")
                .strip()
            )

            if (
                separator_normalized == "."
                and title_line
                and not IETF_SECTION_NUMBER.fullmatch(
                    title_line
                )
            ):
                section_number = (
                    modern_section_match.group(1)
                )

                title = (
                    _clean_rfc_title(
                        title_line
                    )
                )

                if (
                    title
                    and _looks_like_rfc_toc_title(
                        title
                    )
                ):
                    if (
                        section_number
                        not in sections
                    ):
                        sections[
                            section_number
                        ] = title

                    toc_end = i + 2
                    last_match_index = i + 2

                    i += 3
                    continue

        # -------------------------------------------------
        # ÇOK SATIRLI TOC
        # -------------------------------------------------

        section_match = (
            IETF_SECTION_NUMBER.fullmatch(
                stripped
            )
        )

        if section_match:

            section_number = (
                section_match
                .group(1)
            )

            title_lines = []

            j = (
                i + 1
            )

            max_title_end = min(
                len(lines),
                i + 8,
            )

            page_found = False

            while j < max_title_end:

                candidate = (
                    lines[j].strip()
                )

                if not candidate:

                    if (
                        title_lines
                        and j + 1 < max_title_end
                    ):

                        j += 1
                        continue

                    break

                if RFC_PAGE_NUMBER.fullmatch(
                    candidate
                ):

                    combined_title = (
                        " ".join(
                            title_lines
                        )
                    )

                    title = (
                        _clean_rfc_title(
                            combined_title
                        )
                    )

                    if (
                        title_lines
                        and _looks_like_rfc_toc_title(
                            title
                        )
                    ):

                        if (
                            section_number
                            not in sections
                        ):

                            sections[
                                section_number
                            ] = title

                        toc_end = j
                        last_match_index = j

                        page_found = True

                    break

                if (
                    IETF_SECTION_NUMBER.fullmatch(
                        candidate
                    )
                    and title_lines
                ):

                    break

                title_lines.append(
                    candidate
                )

                j += 1

            if page_found:

                i = (
                    j + 1
                )

                continue

        if (
            sections
            and (
                i - last_match_index
            ) > 150
        ):

            break

        i += 1

    return (
        sections,
        toc_start,
        toc_end,
    )


# =========================================================
# IETF HEADING DOĞRULAMA
# =========================================================

def _match_ietf_heading_against_toc(
    lines: list[str],
    index: int,
    toc_sections: dict[str, str],
):

    if index >= len(lines):
        return None

    candidate = (
        lines[index]
        .strip()
    )

    if not candidate:
        return None

    # -------------------------------------------------
    # TEK SATIR
    # -------------------------------------------------

    same_line_match = (
        IETF_SECTION_HEADING.fullmatch(
            candidate
        )
    )

    if same_line_match:

        section_number = (
            same_line_match
            .group(1)
        )

        title = (
            _clean_rfc_title(
                same_line_match
                .group(2)
            )
        )

        expected_title = (
            toc_sections.get(
                section_number
            )
        )

        if (
            expected_title is not None
            and _titles_match(
                title,
                expected_title,
            )
        ):

            return (
                section_number,
                expected_title,
                1,
            )

    # -------------------------------------------------
    # İKİ SATIR
    # -------------------------------------------------

    number_match = (
        IETF_SECTION_NUMBER.fullmatch(
            candidate
        )
    )

    if (
        number_match
        and (
            index + 1
            < len(lines)
        )
    ):

        section_number = (
            number_match
            .group(1)
        )

        expected_title = (
            toc_sections.get(
                section_number
            )
        )

        if expected_title is None:
            return None

        title_candidate = (
            _clean_rfc_title(
                re.sub(
                    r"^\s*\.\s*",
                    "",
                    lines[
                        index + 1
                    ],
                )
            )
        )

        if _titles_match(
            title_candidate,
            expected_title,
        ):

            return (
                section_number,
                expected_title,
                2,
            )

    return None


# =========================================================
# IETF İÇERİK BAŞLANGICI
# =========================================================

def _find_ietf_content_start(
    lines: list[str],
    toc_sections: dict[str, str],
    toc_end: int | None,
) -> int | None:

    if not toc_sections:
        return None

    search_start = (
        (
            toc_end + 1
        )
        if toc_end is not None
        else 0
    )

    first_sections = list(
        toc_sections.keys()
    )[:10]

    first_section_set = set(
        first_sections
    )

    for index in range(
        search_start,
        len(lines),
    ):

        heading = (
            _match_ietf_heading_against_toc(
                lines=lines,
                index=index,
                toc_sections=toc_sections,
            )
        )

        if heading is None:
            continue

        if (
            heading[0]
            in first_section_set
        ):

            return index

    return None


# =========================================================
# IETF FALLBACK HEADING
# =========================================================

def _match_ietf_fallback_heading(
    line: str,
):

    candidate = (
        line.rstrip()
    )

    if not candidate:
        return None

    if (
        candidate
        != candidate.lstrip()
    ):

        return None

    if RFC_TOC_LINE.match(
        candidate
    ):

        return None

    return (
        IETF_SECTION_HEADING.match(
            candidate
        )
    )


# =========================================================
# IETF SPLITTER
# =========================================================

def _split_ietf_clauses(
    document_text: str,
) -> list[
    tuple[str, str, str]
]:

    if not document_text:
        return []

    lines = (
        document_text.splitlines()
    )

    (
        toc_sections,
        _toc_start,
        toc_end,
    ) = (
        _extract_ietf_toc(
            lines
        )
    )

    clauses = []

    current = None

    # -------------------------------------------------
    # TOC VARSA
    # -------------------------------------------------

    if toc_sections:

        content_start = (
            _find_ietf_content_start(
                lines=lines,
                toc_sections=toc_sections,
                toc_end=toc_end,
            )
        )

        if content_start is None:

            content_start = (
                (
                    toc_end + 1
                )
                if toc_end is not None
                else 0
            )

        i = content_start

        seen_sections = set()

        while i < len(lines):

            heading = (
                _match_ietf_heading_against_toc(
                    lines=lines,
                    index=i,
                    toc_sections=toc_sections,
                )
            )

            if heading is not None:

                (
                    section_number,
                    section_title,
                    consumed_lines,
                ) = heading

                if (
                    section_number
                    not in seen_sections
                ):

                    if current:

                        clauses.append(
                            current
                        )

                    current = [
                        section_number,
                        section_title,
                        [],
                    ]

                    seen_sections.add(
                        section_number
                    )

                    i += consumed_lines
                    continue

            if current:

                current[2].append(
                    lines[i]
                )

            i += 1

        if current:

            clauses.append(
                current
            )

        return [
            (
                clause_no,
                clause_title,
                "\n".join(
                    body
                ).strip(),
            )
            for (
                clause_no,
                clause_title,
                body,
            ) in clauses
        ]

    # -------------------------------------------------
    # FALLBACK
    # -------------------------------------------------

    for line in lines:

        match = (
            _match_ietf_fallback_heading(
                line
            )
        )

        if match:

            if current:

                clauses.append(
                    current
                )

            current = [
                match.group(1),
                _clean_rfc_title(
                    match.group(2)
                ),
                [],
            ]

        elif current:

            current[2].append(
                line
            )

    if current:

        clauses.append(
            current
        )

    return [
        (
            clause_no,
            clause_title,
            "\n".join(
                body
            ).strip(),
        )
        for (
            clause_no,
            clause_title,
            body,
        ) in clauses
    ]


# =========================================================
# GENERIC SPLITTER
# =========================================================

def _split_generic_clauses(
    document_text: str,
) -> list[
    tuple[str, str, str]
]:

    lines = (
        document_text.splitlines()
    )

    clauses = []

    current = None

    for line in lines:

        candidate = (
            line.rstrip()
        )

        if not candidate:
            continue

        if (
            candidate
            != candidate.lstrip()
        ):

            if current:

                current[2].append(
                    line
                )

            continue

        match = (
            GENERIC_CLAUSE_HEADING.match(
                candidate
            )
        )

        if match:

            if current:

                clauses.append(
                    current
                )

            current = [
                match.group(1),
                match.group(2).strip(),
                [],
            ]

        elif current:

            current[2].append(
                line
            )

    if current:

        clauses.append(
            current
        )

    return [
        (
            clause_no,
            clause_title,
            "\n".join(
                body
            ).strip(),
        )
        for (
            clause_no,
            clause_title,
            body,
        ) in clauses
    ]


# =========================================================
# ANA CLAUSE SPLITTER
# =========================================================

def split_into_clauses(
    document_text: str,
    doc_org: str,
) -> list[
    tuple[str, str, str]
]:

    if not document_text:
        return []

    org = (
        doc_org
        or ""
    ).strip().upper()

    if org == "IETF":

        return (
            _split_ietf_clauses(
                document_text
            )
        )

    if org == "3GPP":

        return (
            _split_3gpp_clauses(
                document_text
            )
        )

    return (
        _split_generic_clauses(
            document_text
        )
    )


# =========================================================
# UZUN TEXT SPLITTER
# =========================================================

def _split_long_text(
    title: str,
    body: str,
    max_chars: int = MAX_CHUNK_CHARS,
    overlap_chars: int = CHUNK_OVERLAP_CHARS,
) -> list[str]:

    title = (
        title or ""
    ).strip()

    body = (
        body or ""
    ).strip()

    if not body:

        return (
            [title]
            if title
            else []
        )

    full_text = (
        f"{title}\n{body}"
        if title
        else body
    )

    if (
        len(
            full_text
        )
        <= max_chars
    ):

        return [
            full_text
        ]

    chunks = []

    title_size = (
        len(title) + 1
        if title
        else 0
    )

    available_body_chars = (
        max_chars
        - title_size
    )

    if (
        available_body_chars
        <= 0
    ):

        available_body_chars = (
            max_chars
        )

    start = 0

    while start < len(body):

        end = min(
            start
            + available_body_chars,
            len(body),
        )

        if end < len(body):

            search_start = (
                start
                + int(
                    available_body_chars
                    * 0.5
                )
            )

            candidate_end = (
                body.rfind(
                    "\n",
                    search_start,
                    end,
                )
            )

            if (
                candidate_end
                <= start
            ):

                candidate_end = (
                    body.rfind(
                        ". ",
                        search_start,
                        end,
                    )
                )

                if (
                    candidate_end
                    > start
                ):

                    candidate_end += 1

            if (
                candidate_end
                <= start
            ):

                candidate_end = (
                    body.rfind(
                        " ",
                        search_start,
                        end,
                    )
                )

            if (
                candidate_end
                > start
            ):

                end = (
                    candidate_end
                )

        part = (
            body[
                start:end
            ].strip()
        )

        if part:

            if title:

                chunks.append(
                    f"{title}\n{part}"
                )

            else:

                chunks.append(
                    part
                )

        if (
            end
            >= len(body)
        ):

            break

        next_start = max(
            0,
            end - overlap_chars,
        )

        if next_start > 0:

            next_space = (
                body.find(
                    " ",
                    next_start,
                    end,
                )
            )

            if (
                next_space != -1
                and next_space < end
            ):

                next_start = (
                    next_space + 1
                )

        if (
            next_start
            <= start
        ):

            next_start = (
                end
            )

        start = (
            next_start
        )

    return chunks


# =========================================================
# BUILD CHUNKS
# =========================================================

def build_chunks(
    document_text: str,
    doc_org: str,
    doc_code: str,
    version: str,
    source_url: str | None = None,
) -> list[Chunk]:

    chunks = []

    if not document_text:
        return chunks

    clauses = (
        split_into_clauses(
            document_text=document_text,
            doc_org=doc_org,
        )
    )

    for (
        clause_no,
        clause_title,
        body,
    ) in clauses:

        title_clean = (
            clause_title
            or ""
        ).strip()

        body_clean = (
            body
            or ""
        ).strip()

        # -------------------------------------------------
        # ETSI KAPAK / ADRES GÜRÜLTÜSÜ
        # -------------------------------------------------

        if (
            (doc_org or "").strip().upper() == "ETSI"
            and clause_no == "650"
            and "route des lucioles" in title_clean.casefold()
        ):
            continue

        # -------------------------------------------------
        # VOID
        # -------------------------------------------------

        is_void = (
            title_clean
            .casefold()
            .startswith(
                "void"
            )
            or (
                body_clean
                .casefold()
                in {
                    "void",
                    "void.",
                }
            )
        )

        if is_void:

            chunks.append(
                Chunk(
                    text="",
                    doc_org=doc_org,
                    doc_code=doc_code,
                    version=version,
                    clause=clause_no,
                    clause_title=title_clean,
                    status=DocStatus.VOID,
                    source_url=source_url,
                )
            )

            continue

        # -------------------------------------------------
        # NORMAL CHUNK
        # -------------------------------------------------

        text_parts = (
            _split_long_text(
                title=title_clean,
                body=body_clean,
            )
        )

        for text_part in (
            text_parts
        ):

            clean_part = (
                text_part
                or ""
            ).strip()

            if not clean_part:
                continue

            chunks.append(
                Chunk(
                    text=clean_part,
                    doc_org=doc_org,
                    doc_code=doc_code,
                    version=version,
                    clause=clause_no,
                    clause_title=title_clean,
                    status=DocStatus.INDEXED,
                    source_url=source_url,
                )
            )

    return chunks

