import re
from typing import Any


_EXPLANATORY_MARKERS = (
    "ne işe yar",
    "amacı",
    "amaçla",
    "görevi",
    "neden",
    "nasıl",
    "ne demek",
    "ne anlama",
    "avantaj",
    "hangi tür",
    "ne taşın",
    "neyi taşın",
    "ne yönet",
    "hangi işlem",
    "örnek",
    "içeri",
    "davranış",
    "açıkla",
    "anlat",
    "karşılaştır",
    "what does",
    "what is the purpose",
    "why",
    "how does",
    "explain",
)


_EXACT_LOOKUP_PATTERNS: dict[str, tuple[str, ...]] = {
    "SİSTEM": (
        r"\bhangi(?:\s+\w+){0,3}\s+sistem\w*",
        r"\bwhich(?:\s+\w+){0,3}\s+system\b",
    ),
    "MESAJ": (
        r"\bhangi(?:\s+\w+){0,3}\s+mesaj\w*",
        r"\bhangi(?:\s+\w+){0,3}\s+(?:request|message)\b",
        r"\bne\s+gönder\w*",
    ),
    "PROSEDÜR": (
        r"\bhangi(?:\s+\w+){0,3}\s+prosedür\w*",
        r"\bwhich(?:\s+\w+){0,3}\s+procedure\b",
    ),
    "STANDART / DOKÜMAN": (
        r"\bhangi(?:\s+\w+){0,3}\s+(?:standart|standard|doküman|rfc)\w*",
        r"\bwhich(?:\s+\w+){0,3}\s+(?:standard|document|rfc)\b",
    ),
    "ARAYÜZ / REFERANS NOKTASI": (
        r"\bhangi(?:\s+\w+){0,4}\s+(?:arayüz|interface)\w*",
        r"\bhangi(?:\s+\w+){0,4}\s+referans\s+nokt\w*",
        r"\breferans\s+nokt\w*[^?]{0,60}\b(?:hangisidir|nedir|adı\s+ne)\b",
        r"\bwhich(?:\s+\w+){0,4}\s+reference\s+point\b",
    ),
    "PROTOKOL": (
        r"\bhangi(?:\s+\w+){0,4}\s+protokol\w*",
        r"\bwhich(?:\s+\w+){0,4}\s+protocol\b",
    ),
    "DEĞER / LİMİT": (
        r"\bkaç\b",
        r"\b(?:maksimum|minimum|maximum|limit)\b",
        r"\bhow\s+(?:many|much)\b",
    ),
}


_LOW_VALUE_CLAUSE_TITLES = {
    "references",
    "normative references",
    "informative references",
    "bibliography",
    "foreword",
    "change history",
    "history",
    "table of contents",
    "contents",
}


def _normalize_space(value: str) -> str:
    return re.sub(
        r"\s+",
        " ",
        (value or "").strip(),
    )


def _normalize_code(value: str) -> str:
    return _normalize_space(value).casefold()


def extract_document_constraint(
    question: str,
) -> dict[str, str] | None:
    """Soruda açıkça yazılan standart kimliğini metadata filtresine çevirir."""

    value = question or ""

    rfc_match = re.search(
        r"\bRFC\s*[-:]?\s*(\d{3,5})\b",
        value,
        flags=re.IGNORECASE,
    )
    if rfc_match:
        return {
            "org": "IETF",
            "code": rfc_match.group(1),
        }

    organization_match = re.search(
        r"\b(3GPP|ETSI)\s+(TS|TR)\s+"
        r"(\d{2,3})\s*([.\-_ ]?)\s*(\d{3})\b",
        value,
        flags=re.IGNORECASE,
    )
    if organization_match:
        org = organization_match.group(1).upper()
        document_type = organization_match.group(2).upper()
        first = organization_match.group(3)
        separator = organization_match.group(4)
        second = organization_match.group(5)

        if org == "3GPP":
            number = f"{first}.{second}"
        elif separator == ".":
            number = f"{first}.{second}"
        else:
            number = f"{first} {second}"

        return {
            "org": org,
            "code": f"{document_type} {number}",
        }

    generic_spec_match = re.search(
        r"\b(TS|TR)\s+(\d{2})\s*[.\-_ ]\s*(\d{3})\b",
        value,
        flags=re.IGNORECASE,
    )
    if generic_spec_match:
        return {
            "org": "3GPP",
            "code": (
                f"{generic_spec_match.group(1).upper()} "
                f"{generic_spec_match.group(2)}."
                f"{generic_spec_match.group(3)}"
            ),
        }

    return None


def build_chroma_where(
    constraint: dict[str, str] | None,
) -> dict[str, Any] | None:
    if not constraint:
        return None

    return {
        "$and": [
            {"org": constraint["org"]},
            {"code": constraint["code"]},
        ]
    }


def result_matches_document_constraint(
    result: dict[str, Any],
    constraint: dict[str, str] | None,
) -> bool:
    if not constraint:
        return True

    metadata = result.get("metadata", {})
    return (
        _normalize_code(str(metadata.get("org", "")))
        == _normalize_code(constraint["org"])
        and _normalize_code(str(metadata.get("code", "")))
        == _normalize_code(constraint["code"])
    )


def is_multi_part_question(question: str) -> bool:
    value = _normalize_space(question).casefold()

    if value.count("?") > 1 or ";" in value:
        return True

    return re.search(
        r"\bve\b[^?]{0,100}\b"
        r"(?:neden|nasıl|hangi|ne|kaç|what|why|how|which)\b",
        value,
        flags=re.IGNORECASE,
    ) is not None


def is_explanatory_question(question: str) -> bool:
    value = _normalize_space(question).casefold()
    return any(marker in value for marker in _EXPLANATORY_MARKERS)


def allows_deterministic_fast_path(
    question: str,
    answer_type: str,
) -> bool:
    """Yalnızca tek cevaplı kimlik/değer sorularını kısa yola alır."""

    if is_multi_part_question(question):
        return False

    if is_explanatory_question(question):
        return False

    patterns = _EXACT_LOOKUP_PATTERNS.get(answer_type, ())
    if not patterns:
        return False

    value = _normalize_space(question).casefold()
    return any(
        re.search(pattern, value, flags=re.IGNORECASE) is not None
        for pattern in patterns
    )


def is_low_value_clause(
    clause: str,
    clause_title: str,
) -> bool:
    del clause
    title = _normalize_space(clause_title).casefold().strip(" .:-")
    return title in _LOW_VALUE_CLAUSE_TITLES


def build_result_deduplication_key(
    result: dict[str, Any],
) -> tuple[str, ...]:
    metadata = result.get("metadata", {})
    text = _normalize_space(str(result.get("text", ""))).casefold()
    clause = _normalize_space(str(metadata.get("clause", ""))).casefold()
    source_url = _normalize_space(
        str(metadata.get("source_url", ""))
    ).casefold()

    if source_url:
        return (
            "url",
            source_url,
            clause,
            text,
        )

    return (
        "metadata",
        _normalize_code(str(metadata.get("org", ""))),
        _normalize_code(str(metadata.get("code", ""))),
        clause,
        text,
    )


def _question_anchors(question: str) -> list[str]:
    anchors: list[str] = []
    seen: set[str] = set()

    for match in re.finditer(
        r"\b(?:HTTP/3|HTTP|QPACK|QUIC|NGAP|NAS|5GS|5G|"
        r"N\d{1,3}|UE|AMF|SMF|UPF|PUT|DELETE|RFC\s*\d+|"
        r"idempoten\w*|multicast|broadcast|warning\s+message)\b",
        question or "",
        flags=re.IGNORECASE,
    ):
        anchor = _normalize_space(match.group(0)).casefold()
        if anchor in seen:
            continue
        seen.add(anchor)
        anchors.append(anchor)

    return anchors


def has_usable_evidence(
    question: str,
    chunks: list[dict[str, Any]],
) -> bool:
    if not chunks:
        return False

    constraint = extract_document_constraint(question)
    content_chunks = [
        chunk
        for chunk in chunks
        if not is_low_value_clause(
            str(chunk.get("metadata", {}).get("clause", "")),
            str(chunk.get("metadata", {}).get("clause_title", "")),
        )
    ]

    if not content_chunks:
        return False

    if constraint and not any(
        result_matches_document_constraint(chunk, constraint)
        for chunk in content_chunks
    ):
        return False

    haystack = " ".join(
        " ".join(
            (
                str(chunk.get("text", "")),
                str(chunk.get("metadata", {}).get("org", "")),
                str(chunk.get("metadata", {}).get("code", "")),
                str(chunk.get("metadata", {}).get("clause_title", "")),
            )
        )
        for chunk in content_chunks
    ).casefold()

    anchors = _question_anchors(question)
    if anchors and not any(anchor in haystack for anchor in anchors):
        return False

    return True
