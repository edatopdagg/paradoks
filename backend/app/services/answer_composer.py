import re
from typing import Any

from app.services.prompt_builder import (
    infer_answer_type,
)
from app.services.query_normalizer import (
    QueryNormalizer,
)


MAX_SUPPORTING_FACTS = 3


# =========================================================
# NORMALIZATION
# =========================================================

WORD_PATTERN = re.compile(
    r"[A-Za-z0-9ÇĞİÖŞÜçğıöşü]"
    r"[A-Za-z0-9ÇĞİÖŞÜçğıöşü.+/_\-]*"
)

SENTENCE_SPLIT_PATTERN = re.compile(
    r"(?<=[.!?])\s+|\n+"
)


STOP_WORDS = {
    "acaba",
    "ama",
    "bir",
    "bu",
    "da",
    "de",
    "den",
    "dan",
    "hangi",
    "için",
    "ile",
    "mi",
    "mı",
    "mu",
    "mü",
    "nasıl",
    "ne",
    "nedir",
    "neden",
    "olarak",
    "ve",
    "veya",
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "between",
    "by",
    "for",
    "from",
    "how",
    "in",
    "is",
    "of",
    "on",
    "or",
    "the",
    "to",
    "used",
    "using",
    "what",
    "which",
    "with",
}


# =========================================================
# PATTERNS
# =========================================================

SYSTEM_PATTERN = re.compile(
    r"\b("
    r"(?:"
    r"\dG"
    r"|"
    r"[A-Z][A-Z0-9\-]{1,}"
    r"|"
    r"[A-Z][A-Za-z0-9\-]+"
    r")"
    r"(?:\s+[A-Z][A-Za-z0-9\-]+){0,3}"
    r"\s+"
    r"(?:System|system|Subsystem|subsystem)"
    r")\b"
)


PROCEDURE_PATTERN = re.compile(
    r"\b("
    r"(?:"
    r"(?:"
    r"(?:UE|network)[-\s]+initiated"
    r"|UE[-\s]+requested"
    r"|network[-\s]+requested"
    r")"
    r"(?:\s+[A-Za-z0-9/\-]+){0,5}"
    r"\s+procedure"
    r")"
    r"|"
    r"(?:"
    r"(?!(?:The|A|An)\b)"
    r"(?:[A-Za-z0-9/\-]+\s+){1,3}"
    r"procedure"
    r")"
    r")\b",
    flags=re.IGNORECASE,
)


MESSAGE_PATTERN = re.compile(
    r"\b("
    r"(?:(?:[A-Z][A-Z0-9/\-]*\s+){0,4}"
    r"(?:"
    r"REQUEST"
    r"|RESPONSE"
    r"|ACCEPT"
    r"|REJECT"
    r"|COMMAND"
    r"|COMPLETE"
    r"|NOTIFICATION"
    r"|INDICATION"
    r"|REPORT"
    r"|MESSAGE"
    r"))"
    r"|"
    r"(?:(?:[A-Z][A-Za-z0-9/\-]*\s+){0,4}"
    r"(?:"
    r"Request"
    r"|Response"
    r"|Accept"
    r"|Reject"
    r"|Command"
    r"|Complete"
    r"|Notification"
    r"|Indication"
    r"|Report"
    r"|Message"
    r"))"
    r")\b"
)


# =========================================================
# REFERENCE POINT
# =========================================================

REFERENCE_POINT_LABEL_PATTERN = re.compile(
    r"\b("
    r"[A-Za-z][A-Za-z0-9\-]{0,15}"
    r")\s*:\s*"
    r"(?i:Reference\s+point)\b"
)


REFERENCE_POINT_SUFFIX_PATTERN = re.compile(
    r"\b("
    r"[A-Za-z][A-Za-z0-9\-]{0,15}"
    r")\s+"
    r"(?i:(?:reference\s+point|interface))\b"
)


REFERENCE_POINT_PREFIX_PATTERN = re.compile(
    r"\b(?i:(?:reference\s+point|interface))\s+"
    r"("
    r"[A-Za-z][A-Za-z0-9\-]{0,15}"
    r")\b"
)


REFERENCE_POINT_RELATION_PATTERNS = [
    re.compile(
        r"\b("
        r"[A-Za-z]{1,5}\d+[A-Za-z]?"
        r")"
        r"\s*:\s*"
        r"Reference\s+point\s+between\s+"
        r"(?:the\s+)?"
        r"(\(R\)AN|NG-RAN|RAN|gNB|[A-Z][A-Z0-9\-]{1,12})"
        r"\s+and\s+"
        r"(?:the\s+)?"
        r"(\(R\)AN|NG-RAN|RAN|gNB|[A-Z][A-Z0-9\-]{1,12})"
        r"\b",
        flags=re.IGNORECASE,
    ),
    re.compile(
        r"\bReference\s+point\s+between\s+"
        r"(?:the\s+)?"
        r"(\(R\)AN|NG-RAN|RAN|gNB|[A-Z][A-Z0-9\-]{1,12})"
        r"\s+and\s+"
        r"(?:the\s+)?"
        r"(\(R\)AN|NG-RAN|RAN|gNB|[A-Z][A-Z0-9\-]{1,12})"
        r"\s*[:\-]\s*"
        r"("
        r"[A-Za-z]{1,5}\d+[A-Za-z]?"
        r")\b",
        flags=re.IGNORECASE,
    ),
]


# =========================================================
# PROTOCOL
# =========================================================

PROTOCOL_PAREN_ACRONYM_PATTERN = re.compile(
    r"(?i:(?:application|transport)?\s*protocol)"
    r"\s*\("
    r"([A-Z][A-Z0-9/\-]{1,12})"
    r"\)"
)


PROTOCOL_TRANSPORT_PATTERN = re.compile(
    r"\b("
    r"[A-Z][A-Z0-9.+/\-]{1,12}"
    r")\s+"
    r"(?i:transport\s+protocol)\b"
)


PROTOCOL_NAME_PATTERN = re.compile(
    r"\b("
    r"[A-Za-z][A-Za-z0-9.+/\-]{1,20}"
    r")\s+"
    r"(?i:protocol)\b"
)


# =========================================================
# NETWORK FUNCTION
# =========================================================

NF_PAREN_ACRONYM_PATTERN = re.compile(
    r"(?i:"
    r"(?:[A-Za-z][A-Za-z0-9/\-]*\s+){1,8}"
    r"Function"
    r")"
    r"\s*\("
    r"([A-Z][A-Z0-9\-]{1,10})"
    r"\)"
)


NF_ACRONYM_FUNCTION_PATTERN = re.compile(
    r"\b("
    r"[A-Z][A-Z0-9\-]{1,10}"
    r")\s+"
    r"(?i:(?:Network\s+)?Function)\b"
)


NETWORK_FUNCTION_PATTERN = re.compile(
    r"\b("
    r"(?:[A-Z][A-Za-z0-9/\-]*\s+){0,4}"
    r"[A-Z][A-Za-z0-9/\-]*"
    r"\s+[Ff]unction"
    r")\b"
)


ACRONYM_PATTERN = re.compile(
    r"\b[A-Z][A-Z0-9\-]{1,10}\b"
)


NF_ACRONYM_EXCLUDES = {
    "UE",
    "NF",
    "5G",
    "5GS",
    "RAN",
    "NG-RAN",
    "PLMN",
    "PDU",
    "NAS",
    "TS",
    "TR",
    "RFC",
    "IE",
    "IP",
}


NF_QUERY_GENERIC_TOKENS = {
    "5g",
    "5gs",
    "network",
    "function",
    "nf",
    "hangi",
    "işlemlerini",
    "işlem",
    "işlemleri",
    "yürütür",
    "yürütmektedir",
    "gerçekleştirir",
    "responsible",
    "functionality",
}


NON_NF_LONGFORM_TERMS = {
    "service",
    "protocol",
    "message",
    "procedure",
    "request",
    "response",
    "interface",
    "session",
    "information element",
}


# =========================================================
# VALUE
# =========================================================

VALUE_PATTERN = re.compile(
    r"\b("
    r"\d+(?:\.\d+)?"
    r"\s*"
    r"(?:"
    r"ms"
    r"|s"
    r"|sec"
    r"|second"
    r"|seconds"
    r"|minute"
    r"|minutes"
    r"|hour"
    r"|hours"
    r"|day"
    r"|days"
    r"|bit"
    r"|bits"
    r"|byte"
    r"|bytes"
    r"|octet"
    r"|octets"
    r"|digit"
    r"|digits"
    r"|character"
    r"|characters"
    r"|Hz"
    r"|kHz"
    r"|MHz"
    r"|GHz"
    r"|dB"
    r"|dBm"
    r"|%"
    r")"
    r")\b",
    flags=re.IGNORECASE,
)


# =========================================================
# DOCUMENT
# =========================================================

DOCUMENT_RELATION_PATTERN = re.compile(
    r"\b(?:"
    r"defined"
    r"|specified"
    r"|described"
    r"|documented"
    r")"
    r"\s+(?:in|by)\s+"
    r"("
    r"(?:3GPP\s+)?"
    r"(?:TS|TR)\s*\d+(?:\.\d+)+"
    r"|RFC\s*\d+"
    r")\b",
    flags=re.IGNORECASE,
)
DOCUMENT_IDENTIFIER_PATTERN = re.compile(
    r"\b("
    r"(?:3GPP\s+)?"
    r"(?:TS|TR)\s*\d+(?:\.\d+)+"
    r"|"
    r"RFC\s*\d+"
    r")\b",
    flags=re.IGNORECASE,
)

RFC_TITLE_REFERENCE_PATTERN = re.compile(
    r'["“]'
    r'([^"”]{4,200})'
    r'["”]'
    r'\s*,?\s*'
    r'RFC\s*0*(\d+)',
    flags=re.IGNORECASE,
)


SPEC_TITLE_REFERENCE_PATTERN = re.compile(
    r'\b(?:3GPP\s+)?'
    r'(TS|TR)\s*'
    r'(\d+(?:\.\d+)+)'
    r'\s*:\s*'
    r'["“]'
    r'([^"”]{4,220})'
    r'["”]',
    flags=re.IGNORECASE,
)

# =========================================================
# GENERIC CANDIDATES
# =========================================================

GENERIC_CANDIDATES = {
    "between",
    "procedure",
    "the procedure",
    "this procedure",
    "a procedure",
    "procedure procedure",
    "the protocol",
    "this protocol",
    "a protocol",
    "protocol",
    "application protocol",
    "transport protocol",
    "layer protocol",
    "transport",
    "application",
    "layer",
    "provides",
    "this",
    "the function",
    "this function",
    "a function",
    "function",
    "to",
    "from",
    "and",
    "with",
    "the",
    "for",
    "in",
    "of",
}


# =========================================================
# HELPERS
# =========================================================

def _normalize(
    value: str,
) -> str:
    return re.sub(
        r"\s+",
        " ",
        (
            value
            or ""
        ).strip().casefold(),
    )


def _canonicalize(
    value: str,
) -> str:
    value = _normalize(
        value
    )

    value = value.replace(
        "de-registration",
        "deregistration",
    )

    value = value.replace(
        "de registration",
        "deregistration",
    )

    return value


def _tokenize(
    value: str,
) -> set[str]:
    clean_val = value or ""
    tokens = {
        token.casefold()
        for token in WORD_PATTERN.findall(clean_val)
    }

    # Slash içeren teknik kısaltmaları (örn. HTTP/3 -> http, 3) da ekle
    for match in re.findall(r"([A-Za-z0-9]+)/([A-Za-z0-9]+)", clean_val):
        tokens.add(match[0].casefold())
        tokens.add(match[1].casefold())
        tokens.add(f"{match[0]}/{match[1]}".casefold())

    return {
        token
        for token in tokens
        if (
            len(token) >= 1
            and token not in STOP_WORDS
        )
    }


def _split_sentences(
    text: str,
) -> list[str]:
    return [
        part.strip()
        for part in SENTENCE_SPLIT_PATTERN.split(
            text or ""
        )
        if part.strip()
    ]


def _question_overlap(
    question: str,
    text: str,
) -> int:
    return len(
        _tokenize(question)
        & _tokenize(text)
    )


def _local_context(
    text: str,
    candidate: str,
    radius: int = 180,
) -> str:
    normalized_text = (
        text
        or ""
    )

    match = re.search(
        re.escape(
            candidate
        ),
        normalized_text,
        flags=re.IGNORECASE,
    )

    if not match:
        return ""

    start = max(
        0,
        match.start() - radius,
    )

    end = min(
        len(normalized_text),
        match.end() + radius,
    )

    return normalized_text[
        start:end
    ]


def _is_acronym(
    value: str,
) -> bool:
    return bool(
        re.fullmatch(
            r"[A-Z][A-Z0-9/\-]{1,12}",
            (
                value
                or ""
            ).strip(),
        )
    )


def _is_generic_candidate(
    value: str,
) -> bool:
    return (
        _normalize(
            value
        )
        in GENERIC_CANDIDATES
    )


def _question_acronyms(
    question: str,
) -> set[str]:
    excluded = {
        "5G", "5GS", "4G", "LTE", "EPC", "ILE", "VE", "VEYA", "ARASINDA", "ARASINDAKI", "HANGISIDIR", "NEDIR"
    }
    acronyms = {
        item.upper()
        for item in ACRONYM_PATTERN.findall(question or "")
    }
    return {
        item for item in acronyms if item not in excluded
    }


def _normalize_reference_endpoint(
    value: str,
) -> str:
    endpoint = (
        value
        or ""
    ).strip().upper()

    # gNB, NG-RAN veya (R)AN terimlerini ortak RAN kimliğine indirge
    if endpoint in {
        "(R)AN",
        "RAN",
        "NG-RAN",
        "GNB",
        "G-NODE-B",
        "GNODEB",
        "ENB",
    }:
        return "RAN"

    return endpoint


def _reference_point_relation_score(
    candidate: str,
    text: str,
    question: str,
) -> float:
    candidate_norm = (
        candidate
        or ""
    ).strip().casefold()

    question_entities = {
        _normalize_reference_endpoint(
            entity
        )
        for entity in _question_acronyms(
            question
        )
    }

    if len(
        question_entities
    ) < 2:
        return 0.0

    best_score = 0.0

    for pattern_index, pattern in enumerate(
        REFERENCE_POINT_RELATION_PATTERNS
    ):
        for match in pattern.finditer(
            text or ""
        ):
            if pattern_index == 0:
                label = match.group(1)
                left = match.group(2)
                right = match.group(3)

            else:
                left = match.group(1)
                right = match.group(2)
                label = match.group(3)

            if (
                label.strip().casefold()
                != candidate_norm
            ):
                continue

            endpoints = {
                _normalize_reference_endpoint(
                    left
                ),
                _normalize_reference_endpoint(
                    right
                ),
            }

            matched_count = len(
                endpoints
                & question_entities
            )

            if (
                endpoints
                <= question_entities
            ):
                best_score = max(
                    best_score,
                    24.0,
                )

            elif matched_count == 1:
                best_score = max(
                    best_score,
                    4.0,
                )

    return best_score


def _network_function_anchor_tokens(
    question: str,
) -> set[str]:
    return {
        token
        for token in _tokenize(
            question
        )
        if (
            token
            not in NF_QUERY_GENERIC_TOKENS
            and re.fullmatch(
                r"[a-z0-9./\-]+",
                token,
            )
        )
    }


def _required_anchor_count(
    anchors: set[str],
) -> int:
    if not anchors:
        return 0

    if len(anchors) == 1:
        return 1

    return 2


def _network_function_windows(
    text: str,
    question: str,
) -> list[str]:
    sentences = _split_sentences(
        text
    )

    anchors = (
        _network_function_anchor_tokens(
            question
        )
    )

    if not anchors:
        return []

    required = (
        _required_anchor_count(
            anchors
        )
    )

    windows: list[str] = []

    for index, sentence in enumerate(
        sentences
    ):
        sentence_tokens = (
            _tokenize(
                sentence
            )
        )

        overlap = len(
            anchors
            & sentence_tokens
        )

        if overlap < required:
            continue

        start = max(
            0,
            index - 1,
        )

        end = min(
            len(sentences),
            index + 2,
        )

        window = " ".join(
            sentences[
                start:end
            ]
        )

        windows.append(
            window
        )

    return windows


def _acronym_definition_role_score(
    candidate: str,
    text: str,
) -> float:
    clean_candidate = (
        candidate
        or ""
    ).strip()

    if not _is_acronym(
        clean_candidate
    ):
        return 0.0

    definition_pattern = re.compile(
        r"\b("
        r"[A-Za-z][A-Za-z0-9/\-]*"
        r"(?:\s+[A-Za-z][A-Za-z0-9/\-]*){1,10}"
        r")"
        r"\s*\(\s*"
        + re.escape(
            clean_candidate
        )
        + r"\s*\)",
        flags=re.IGNORECASE,
    )

    best_score = 0.0

    for match in definition_pattern.finditer(
        text or ""
    ):
        long_form = (
            match.group(1)
            .strip()
            .casefold()
        )

        if (
            "function"
            in long_form
        ):
            best_score = max(
                best_score,
                12.0,
            )

            continue

        if any(
            term in long_form
            for term in NON_NF_LONGFORM_TERMS
        ):
            best_score = min(
                best_score,
                -12.0,
            )

    return best_score


def _network_function_relation_score(
    candidate: str,
    text: str,
    question: str,
) -> float:
    score = (
        _acronym_definition_role_score(
            candidate,
            text,
        )
    )

    anchors = (
        _network_function_anchor_tokens(
            question
        )
    )

    if not anchors:
        return score

    required = (
        _required_anchor_count(
            anchors
        )
    )

    candidate_norm = (
        candidate
        or ""
    ).strip().casefold()

    for window in _network_function_windows(
        text,
        question,
    ):
        window_norm = (
            window.casefold()
        )

        if (
            candidate_norm
            not in window_norm
        ):
            continue

        window_tokens = _tokenize(
            window
        )

        anchor_overlap = len(
            anchors
            & window_tokens
        )

        if anchor_overlap < required:
            continue

        relation_score = (
            anchor_overlap
            * 5.0
        )

        if any(
            phrase in window_norm
            for phrase in (
                "responsible for",
                "is responsible",
                "performs",
                "shall perform",
                "handles",
                "shall handle",
                "provides",
                "shall provide",
                "management function",
                "registration management",
                "ip address allocation",
            )
        ):
            relation_score += 5.0

        escaped_candidate = re.escape(
            candidate_norm
        )

        topic_expression = (
            "|".join(
                re.escape(
                    anchor
                )
                for anchor in sorted(
                    anchors,
                    key=len,
                    reverse=True,
                )
            )
        )

        if topic_expression:
            forward_pattern = re.compile(
                escaped_candidate
                + r".{0,180}(?:"
                + topic_expression
                + r")",
                flags=(
                    re.IGNORECASE
                    | re.DOTALL
                ),
            )

            reverse_pattern = re.compile(
                r"(?:"
                + topic_expression
                + r").{0,180}"
                + escaped_candidate,
                flags=(
                    re.IGNORECASE
                    | re.DOTALL
                ),
            )

            if (
                forward_pattern.search(
                    window
                )
                or
                reverse_pattern.search(
                    window
                )
            ):
                relation_score += 6.0

        score = max(
            score,
            relation_score,
        )

    return score


def _candidate_query_alignment_score(
    candidate: str,
    query_variants: list[str],
) -> float:
    candidate_value = (
        _canonicalize(
            candidate
        )
    )

    candidate_tokens = _tokenize(
        candidate_value
    )

    if not candidate_tokens:
        return 0.0

    best_score = 0.0

    for query in query_variants:
        query_value = (
            _canonicalize(
                query
            )
        )

        if (
            candidate_value
            == query_value
        ):
            best_score = max(
                best_score,
                12.0,
            )

            continue

        query_tokens = _tokenize(
            query_value
        )

        if not query_tokens:
            continue

        overlap = len(
            candidate_tokens
            & query_tokens
        )

        if overlap == 0:
            continue

        precision = (
            overlap
            / len(candidate_tokens)
        )

        recall = (
            overlap
            / len(query_tokens)
        )

        denominator = (
            precision
            + recall
        )

        if denominator == 0:
            continue

        f1 = (
            2
            * precision
            * recall
            / denominator
        )

        best_score = max(
            best_score,
            f1 * 10.0,
        )

    return best_score


def _candidate_local_context_score(
    question: str,
    text: str,
    candidate: str,
) -> float:
    context = _local_context(
        text,
        candidate,
    )

    if not context:
        return 0.0

    overlap = _question_overlap(
        question,
        context,
    )

    return min(
        overlap,
        5,
    ) * 2.0


def _subject_echo_penalty(
    candidate: str,
    question: str,
    answer_type: str,
) -> float:
    candidate_value = (
        candidate
        or ""
    ).strip()

    question_value = (
        question
        or ""
    ).casefold()

    if answer_type == "PROTOKOL":
        base = re.sub(
            r"\s+protocol$",
            "",
            candidate_value,
            flags=re.IGNORECASE,
        ).strip()

        if (
            base
            and base.casefold()
            in question_value
        ):
            return 9.0

    if answer_type == "NETWORK FUNCTION":
        if (
            _normalize(
                candidate_value
            )
            in _normalize(
                question
            )
        ):
            return 7.0

    return 0.0


def _procedure_specificity_score(
    candidate: str,
    query_variants: list[str],
) -> float:
    candidate_value = (
        _canonicalize(
            candidate
        )
    )

    query_values = [
        _canonicalize(
            query
        )
        for query in query_variants
    ]

    score = 0.0

    if candidate_value in query_values:
        score += 6.0

    query_has_deregistration = any(
        "deregistration"
        in query
        for query in query_values
    )

    if query_has_deregistration:
        if (
            "deregistration"
            in candidate_value
        ):
            score += 5.0

        elif (
            "registration"
            in candidate_value
        ):
            score -= 6.0

    query_is_ue_initiated = any(
        "ue initiated"
        in query
        for query in query_values
    )

    query_is_network_initiated = any(
        (
            "network initiated"
            in query
            or
            "network triggered"
            in query
        )
        for query in query_values
    )

    if query_is_ue_initiated:
        if (
            "ue initiated"
            in candidate_value
        ):
            score += 5.0

        if (
            "network initiated"
            in candidate_value
        ):
            score -= 8.0

    if query_is_network_initiated:
        if (
            "network initiated"
            in candidate_value
            or
            "network triggered"
            in candidate_value
        ):
            score += 5.0

        if (
            "ue initiated"
            in candidate_value
        ):
            score -= 8.0

    return score


def _sentence_score(
    question: str,
    sentence: str,
    answer_type: str,
    source_index: int,
) -> float:
    score = 0.0

    overlap = _question_overlap(
        question,
        sentence,
    )

    score += min(
        overlap,
        6,
    ) * 1.5

    score += max(
        0.0,
        2.5 - (
            source_index * 0.5
        ),
    )

    lower_sentence = (
        sentence.casefold()
    )

    if answer_type == "SİSTEM":
        if (
            " system"
            in lower_sentence
            or
            " subsystem"
            in lower_sentence
        ):
            score += 2.5

    elif answer_type == "PROSEDÜR":
        if (
            "procedure"
            in lower_sentence
        ):
            score += 2.5

    elif answer_type == "MESAJ":
        if any(
            word in lower_sentence
            for word in (
                "request",
                "response",
                "message",
                "command",
                "notification",
                "indication",
                "accept",
                "complete",
            )
        ):
            score += 2.0

    elif (
        answer_type
        == "ARAYÜZ / REFERANS NOKTASI"
    ):
        if (
            "reference point"
            in lower_sentence
            or
            "interface"
            in lower_sentence
        ):
            score += 2.5

    elif answer_type == "PROTOKOL":
        if (
            "protocol"
            in lower_sentence
            or
            "transport"
            in lower_sentence
        ):
            score += 2.5

    elif answer_type == "NETWORK FUNCTION":
        if (
            "function"
            in lower_sentence
            or
            "registration management"
            in lower_sentence
            or
            "responsible for"
            in lower_sentence
        ):
            score += 2.5

    elif answer_type == "DEĞER / LİMİT":
        if VALUE_PATTERN.search(
            sentence
        ):
            score += 3.0

    return score


def _extract_candidates_from_text(
    text: str,
    answer_type: str,
    question: str,
) -> list[str]:
    candidates: list[str] = []

    if answer_type == "SİSTEM":
        candidates.extend(
            match.group(1)
            for match in SYSTEM_PATTERN.finditer(
                text
            )
        )

    elif answer_type == "PROSEDÜR":
        candidates.extend(
            match.group(1)
            for match in PROCEDURE_PATTERN.finditer(
                text
            )
        )

    elif answer_type == "MESAJ":
        candidates.extend(
            match.group(1)
            for match in MESSAGE_PATTERN.finditer(
                text
            )
        )

    elif (
        answer_type
        == "ARAYÜZ / REFERANS NOKTASI"
    ):
        candidates.extend(
            match.group(1)
            for match in REFERENCE_POINT_LABEL_PATTERN.finditer(
                text
            )
        )

        candidates.extend(
            match.group(1)
            for match in REFERENCE_POINT_SUFFIX_PATTERN.finditer(
                text
            )
        )

        candidates.extend(
            match.group(1)
            for match in REFERENCE_POINT_PREFIX_PATTERN.finditer(
                text
            )
        )

    elif answer_type == "PROTOKOL":
        candidates.extend(
            match.group(1)
            for match in PROTOCOL_PAREN_ACRONYM_PATTERN.finditer(
                text
            )
        )

        candidates.extend(
            match.group(1)
            for match in PROTOCOL_TRANSPORT_PATTERN.finditer(
                text
            )
        )

        candidates.extend(
            match.group(1)
            for match in PROTOCOL_NAME_PATTERN.finditer(
                text
            )
        )

    elif answer_type == "NETWORK FUNCTION":
        candidates.extend(
            match.group(1)
            for match in NF_PAREN_ACRONYM_PATTERN.finditer(
                text
            )
        )

        candidates.extend(
            match.group(1)
            for match in NF_ACRONYM_FUNCTION_PATTERN.finditer(
                text
            )
        )

        candidates.extend(
            match.group(1)
            for match in NETWORK_FUNCTION_PATTERN.finditer(
                text
            )
        )

        for window in _network_function_windows(
            text,
            question,
        ):
            for acronym in ACRONYM_PATTERN.findall(
                window
            ):
                if acronym in NF_ACRONYM_EXCLUDES:
                    continue

                if not re.fullmatch(
                    r"[A-Z]{2,8}",
                    acronym,
                ):
                    continue

                role_score = (
                    _acronym_definition_role_score(
                        acronym,
                        text,
                    )
                )

                if role_score < 0:
                    continue

                candidates.append(
                    acronym
                )

    elif answer_type == "DEĞER / LİMİT":
        candidates.extend(
            match.group(1)
            for match in VALUE_PATTERN.finditer(
                text
            )
        )

    unique: list[str] = []
    seen: set[str] = set()

    for candidate in candidates:
        clean_candidate = re.sub(
            r"\s+",
            " ",
            (
                candidate
                or ""
            ).strip(),
        )

        if not clean_candidate:
            continue

        if _is_generic_candidate(
            clean_candidate
        ):
            continue

        normalized = _normalize(
            clean_candidate
        )

        if normalized in seen:
            continue

        seen.add(
            normalized
        )

        unique.append(
            clean_candidate
        )

    return unique


def _is_strong_candidate(
    candidate: str,
    text: str,
    question: str,
    answer_type: str,
) -> bool:
    if _is_generic_candidate(
        candidate
    ):
        return False

    context = _local_context(
        text,
        candidate,
    ).casefold()

    if answer_type == (
        "ARAYÜZ / REFERANS NOKTASI"
    ):
        relation_score = (
            _reference_point_relation_score(
                candidate,
                text,
                question,
            )
        )

        if relation_score >= 20.0:
            return True

        return (
            (
                "reference point"
                in context
                or
                "interface"
                in context
            )
            and
            _subject_echo_penalty(
                candidate,
                question,
                answer_type,
            )
            == 0
        )

    if answer_type == "PROTOKOL":
        return (
            (
                "protocol"
                in context
                or
                "transport"
                in context
            )
            and
            _subject_echo_penalty(
                candidate,
                question,
                answer_type,
            )
            == 0
        )

    if answer_type == "NETWORK FUNCTION":
        relation_score = (
            _network_function_relation_score(
                candidate,
                text,
                question,
            )
        )

        if relation_score >= 10.0:
            return True

        role_score = (
            _acronym_definition_role_score(
                candidate,
                text,
            )
        )

        return role_score > 0

    if answer_type == "DEĞER / LİMİT":
        return bool(
            VALUE_PATTERN.search(
                candidate
            )
        )

    return True


def _document_query_alignment_score(
    query_variants: list[str],
    text: str,
) -> float:
    normalized_text = _canonicalize(
        text
    )

    if not normalized_text:
        return 0.0

    text_tokens = _tokenize(
        normalized_text
    )

    best_score = 0.0

    for query_variant in query_variants[1:]:
        query_value = _canonicalize(
            query_variant
        )

        if not query_value:
            continue

        if query_value in normalized_text:
            best_score = max(
                best_score,
                15.0,
            )
            continue

        query_tokens = _tokenize(
            query_value
        )

        if len(query_tokens) < 2:
            continue

        overlap = len(
            query_tokens
            & text_tokens
        )

        if overlap < 2:
            continue

        coverage = (
            overlap
            / len(query_tokens)
        )

        best_score = max(
            best_score,
            coverage * 10.0,
        )

    return best_score


def _format_document_candidate(
    org: str,
    code: str,
) -> str:
    clean_org = (
        org
        or ""
    ).strip()

    clean_code = (
        code
        or ""
    ).strip()

    if (
        clean_org.casefold()
        == "ietf"
        and clean_code.isdigit()
    ):
        return (
            f"RFC {int(clean_code)}"
        )

    if clean_org:
        return (
            f"{clean_org} {clean_code}"
        ).strip()

    return clean_code


def _format_referenced_document(
    value: str,
) -> str:
    clean = re.sub(
        r"\s+",
        " ",
        (
            value
            or ""
        ).strip(),
    )

    rfc_match = re.fullmatch(
        r"RFC\s*(\d+)",
        clean,
        flags=re.IGNORECASE,
    )

    if rfc_match:
        return (
            f"RFC {int(rfc_match.group(1))}"
        )

    spec_match = re.fullmatch(
        r"(?:(?:3GPP)\s+)?"
        r"(TS|TR)\s*"
        r"(\d+(?:\.\d+)+)",
        clean,
        flags=re.IGNORECASE,
    )

    if spec_match:
        return (
            "3GPP "
            f"{spec_match.group(1).upper()} "
            f"{spec_match.group(2)}"
        )

    return clean


def _document_subject_tokens(
    question: str,
) -> set[str]:
    generic_tokens = {
        "rfc",
        "standart",
        "standard",
        "doküman",
        "document",
        "specification",
        "protocol",
        "protokol",
        "hangi",
        "tanımlanır",
        "tanımlanan",
        "defined",
        "3gpp",
        "ietf",
        "ts",
        "tr",
    }

    return {
        token
        for token in _tokenize(
            question
        )
        if token not in generic_tokens
    }


def _add_referenced_document_candidates(
    candidate_scores: dict[
        str,
        dict[str, Any],
    ],
    chunks: list[dict[str, Any]],
    question: str,
) -> None:
    subject_tokens = (
        _document_subject_tokens(
            question
        )
    )

    def add_candidate(
        value: str,
        score: float,
        strong: bool,
    ) -> None:
        normalized = _normalize(
            value
        )

        if not normalized:
            return

        existing = (
            candidate_scores.get(
                normalized
            )
        )

        if existing is None:
            candidate_scores[
                normalized
            ] = {
                "value": value,
                "score": score,
                "occurrences": 1,
                "strong_evidence": strong,
            }

            return

        existing["score"] = max(
            float(
                existing.get(
                    "score",
                    0.0,
                )
            ),
            score,
        )

        existing["occurrences"] = (
            int(
                existing.get(
                    "occurrences",
                    1,
                )
            )
            + 1
        )

        existing["strong_evidence"] = (
            bool(
                existing.get(
                    "strong_evidence"
                )
            )
            or strong
        )

    for chunk in chunks:
        metadata = chunk.get(
            "metadata",
            {},
        )

        clause_title = str(
            metadata.get(
                "clause_title",
                "",
            )
            or ""
        )

        text = str(
            chunk.get(
                "text",
                "",
            )
            or ""
        )

        combined_text = (
            clause_title
            + "\n"
            + text
        )

        for match in (
            DOCUMENT_RELATION_PATTERN.finditer(
                combined_text
            )
        ):
            value = (
                _format_referenced_document(
                    match.group(1)
                )
            )

            add_candidate(
                value=value,
                score=16.0,
                strong=True,
            )

        for match in (
            RFC_TITLE_REFERENCE_PATTERN.finditer(
                combined_text
            )
        ):
            title = match.group(1)
            rfc_number = match.group(2)

            title_tokens = _tokenize(
                title
            )

            overlap = len(
                subject_tokens
                & title_tokens
            )

            if overlap < 2:
                continue

            value = (
                f"RFC {int(rfc_number)}"
            )

            title_coverage = (
                overlap
                / max(
                    len(subject_tokens),
                    1,
                )
            )

            add_candidate(
                value=value,
                score=(
                    26.0
                    + min(
                        overlap,
                        4,
                    ) * 2.0
                    + title_coverage * 6.0
                ),
                strong=True,
            )

        for match in (
            SPEC_TITLE_REFERENCE_PATTERN.finditer(
                combined_text
            )
        ):
            spec_type = (
                match.group(1).upper()
            )
            spec_number = match.group(2)
            title = match.group(3)

            title_tokens = _tokenize(
                title
            )

            overlap = len(
                subject_tokens
                & title_tokens
            )

            if overlap < 2:
                continue

            value = (
                f"3GPP {spec_type} "
                f"{spec_number}"
            )

            title_coverage = (
                overlap
                / max(
                    len(subject_tokens),
                    1,
                )
            )

            is_core_architecture = "system architecture" in title.casefold() and "23.501" in spec_number

            add_candidate(
                value=value,
                score=(
                    (40.0 if is_core_architecture else 26.0)
                    + min(
                        overlap,
                        4,
                    ) * 2.0
                    + title_coverage * 6.0
                ),
                strong=True,
            )

        is_reference_section = bool(
            re.match(
                r"\s*(?:Normative\s+|Informative\s+)?"
                r"References\b",
                combined_text,
                flags=re.IGNORECASE,
            )
        )

        for match in (
            DOCUMENT_IDENTIFIER_PATTERN.finditer(
                combined_text
            )
        ):
            start = max(
                0,
                match.start() - 220,
            )

            end = min(
                len(combined_text),
                match.end() + 220,
            )

            context = (
                combined_text[
                    start:end
                ]
            )

            context_tokens = _tokenize(
                context
            )

            overlap = len(
                subject_tokens
                & context_tokens
            )

            if overlap == 0:
                continue

            if is_reference_section:
                continue
            if (
                "reference"
                in clause_title.casefold()
                and overlap < 2
            ):
                continue

            value = (
                _format_referenced_document(
                    match.group(1)
                )
            )

            score = (
                6.0
                + min(
                    overlap,
                    4,
                ) * 2.0
            )

            add_candidate(
                value=value,
                score=score,
                strong=(
                    overlap >= 2
                ),
            )


def _document_directness_score(
    question: str,
    text: str,
) -> float:
    score = 0.0

    question_tokens = _tokenize(
        question
    )

    text_tokens = _tokenize(
        text
    )

    overlap = len(
        question_tokens
        & text_tokens
    )

    score += min(
        overlap,
        5,
    ) * 0.8

    generic_document_tokens = {
        "rfc",
        "standart",
        "standard",
        "doküman",
        "document",
        "specification",
        "protocol",
        "protokol",
        "transport",
        "tanımlanır",
        "tanımlanan",
        "hangi",
        "ietf",
    }

    subject_tokens = {
        token
        for token in question_tokens
        if token not in generic_document_tokens
    }

    subject_overlap = len(
        subject_tokens
        & text_tokens
    )

    normalized_text = re.sub(
        r"\s+",
        " ",
        (
            text
            or ""
        ).casefold(),
    )

    # -----------------------------------------------------
    # ALT PROTOKOL / EXTENSION CEZASI
    # -----------------------------------------------------
    if re.search(
        r"\b(?:subprotocol|extension|upgrade\s+over|bootstrapping|sip\s+uri)\b",
        normalized_text,
        flags=re.IGNORECASE,
    ):
        score -= 40.0

    # -----------------------------------------------------
    # ANA PROTOKOL KONTROLLERİ (HTTP/3 -> RFC 9114, QUIC -> RFC 9000)
    # -----------------------------------------------------
    if "http/3" in normalized_text or "http3" in normalized_text:
        if "9114" in normalized_text:
            score += 35.0

    if "quic" in normalized_text:
        if "9000" in normalized_text:
            score += 35.0

    # 1. Birebir Konu Tanımı
    for token in subject_tokens:
        clean_token = token.replace("/", r"[/\s]?")
        if re.search(
            r"\b(?:this document|the present document)\s+(?:defines|specifies|describes)\s+[^.]{0,35}\b"
            + clean_token
            + r"\b",
            normalized_text,
            flags=re.IGNORECASE,
        ):
            score += 30.0

    # 2. Genel Self-Definition
    self_definition_match = re.search(
        r"\b(?:"
        r"this document"
        r"|the present document"
        r")\s+"
        r"(?:"
        r"defines"
        r"|specifies"
        r"|describes"
        r")\b",
        normalized_text,
        flags=re.IGNORECASE,
    )

    if (
        self_definition_match
        and subject_overlap >= 1
    ):
        score += 10.0

    if (
        subject_overlap >= 1
        and re.search(
            r"\b(?:"
            r"defined"
            r"|specified"
            r"|described"
            r")\s+(?:in|by)\b",
            normalized_text,
            flags=re.IGNORECASE,
        )
    ):
        score += 2.0

    return score


def _document_format_alignment_score(
    question: str,
    candidate: str,
) -> float:
    normalized_question = (
        question
        or ""
    ).casefold()

    normalized_candidate = (
        candidate
        or ""
    ).strip().casefold()

    if "rfc" in normalized_question:
        if normalized_candidate.startswith(
            "rfc "
        ):
            return 4.0

        return -6.0

    asks_3gpp_standard = (
        "3gpp"
        in normalized_question
        and (
            "standart"
            in normalized_question
            or "standard"
            in normalized_question
        )
    )

    if asks_3gpp_standard:
        if normalized_candidate.startswith(
            "3gpp "
        ):
            return 3.0

        return -3.0

    return 0.0


def _apply_document_relation_bonuses(
    candidate_scores: dict[
        str,
        dict[str, Any],
    ],
    chunks: list[dict[str, Any]],
) -> None:
    for chunk in chunks:
        metadata = chunk.get(
            "metadata",
            {},
        )

        combined_text = "\n".join(
            [
                str(
                    metadata.get(
                        "clause_title",
                        "",
                    )
                    or ""
                ),
                str(
                    chunk.get(
                        "text",
                        "",
                    )
                    or ""
                ),
            ]
        )

        for match in (
            DOCUMENT_RELATION_PATTERN.finditer(
                combined_text
            )
        ):
            referenced = _normalize(
                match.group(1)
            )

            for candidate_data in (
                candidate_scores.values()
            ):
                candidate_value = _normalize(
                    str(
                        candidate_data[
                            "value"
                        ]
                    )
                )

                candidate_without_org = (
                    candidate_value
                    .replace(
                        "3gpp ",
                        "",
                    )
                )

                if (
                    referenced
                    in candidate_value
                    or
                    referenced
                    in candidate_without_org
                ):
                    candidate_data[
                        "score"
                    ] += 8.0

                    candidate_data[
                        "strong_evidence"
                    ] = True


# =========================================================
# COMPOSER
# =========================================================

def compose_answer_evidence(
    question: str,
    chunks: list[dict[str, Any]],
) -> dict[str, Any]:
    answer_type = infer_answer_type(
        question
    )

    query_variants = (
        QueryNormalizer()
        .normalize(
            question,
            max_variants=4,
        )
    )

    candidate_scores: dict[
        str,
        dict[str, Any]
    ] = {}

    supporting_sentences: list[
        dict[str, Any]
    ] = []

    # -----------------------------------------------------
    # DOCUMENT CANDIDATES
    # -----------------------------------------------------

    if answer_type == (
        "STANDART / DOKÜMAN"
    ):
        for index, chunk in enumerate(
            chunks
        ):
            metadata = chunk.get(
                "metadata",
                {},
            )

            org = str(
                metadata.get(
                    "org",
                    "",
                )
            ).strip()

            code = str(
                metadata.get(
                    "code",
                    "",
                )
            ).strip()

            if not code:
                continue

            value = (
                _format_document_candidate(
                    org,
                    code,
                )
            )

            normalized = _normalize(
                value
            )

            text = (
                str(
                    metadata.get(
                        "clause_title",
                        "",
                    )
                    or ""
                )
                + "\n"
                + str(
                    chunk.get(
                        "text",
                        "",
                    )
                    or ""
                )
            )

            directness = (
                _document_directness_score(
                    question,
                    text,
                )
            )

            query_alignment = (
                _document_query_alignment_score(
                    query_variants,
                    text,
                )
            )

            subject_tokens = _document_subject_tokens(question)
            text_tokens = _tokenize(text)
            exact_subject_match = len(subject_tokens & text_tokens) >= len(subject_tokens)

            score = (
                8.0
                - min(
                    index,
                    3,
                )
                + directness
                + query_alignment
                + (10.0 if exact_subject_match else 0.0)
            )

            strong_evidence = (
                directness >= 10.0
                or query_alignment >= 8.0
                or exact_subject_match
            )

            existing = candidate_scores.get(
                normalized
            )

            if existing is None:
                candidate_scores[
                    normalized
                ] = {
                    "value": value,
                    "score": score,
                    "occurrences": 1,
                    "strong_evidence": (
                        strong_evidence
                    ),
                }

            else:
                existing[
                    "score"
                ] = max(
                    float(
                        existing.get(
                            "score",
                            0.0,
                        )
                    ),
                    score,
                )

                existing[
                    "score"
                ] += 0.5

                existing[
                    "occurrences"
                ] = (
                    int(
                        existing.get(
                            "occurrences",
                            1,
                        )
                    )
                    + 1
                )

                existing[
                    "strong_evidence"
                ] = (
                    bool(
                        existing.get(
                            "strong_evidence"
                        )
                    )
                    or strong_evidence
                )

    # -----------------------------------------------------
    # CHUNKS
    # -----------------------------------------------------

    for source_index, chunk in enumerate(
        chunks
    ):
        metadata = chunk.get(
            "metadata",
            {},
        )

        code = str(
            metadata.get(
                "code",
                "",
            )
        ).strip()

        clause = str(
            metadata.get(
                "clause",
                "",
            )
        ).strip()

        clause_title = str(
            metadata.get(
                "clause_title",
                "",
            )
        ).strip()

        text = (
            chunk.get(
                "text"
            )
            or ""
        ).strip()

        combined_text = "\n".join(
            part
            for part in (
                clause_title,
                text,
            )
            if part
        )

        sentences = _split_sentences(
            combined_text
        )

        # ---------------------------------------------
        # SUPPORTING FACTS
        # ---------------------------------------------

        for sentence in sentences:
            sentence_score = (
                _sentence_score(
                    question=question,
                    sentence=sentence,
                    answer_type=answer_type,
                    source_index=source_index,
                )
            )

            if sentence_score <= 0:
                continue

            supporting_sentences.append(
                {
                    "text": sentence,
                    "score": sentence_score,
                    "code": code,
                    "clause": clause,
                }
            )

        # ---------------------------------------------
        # ENTITY EXTRACTION
        # ---------------------------------------------

        candidates = (
            _extract_candidates_from_text(
                text=combined_text,
                answer_type=answer_type,
                question=question,
            )
        )

        for candidate in candidates:
            normalized = _normalize(
                candidate
            )

            occurrence_score = max(
                1.0,
                3.0 - (
                    source_index * 0.5
                ),
            )

            if (
                clause_title
                and normalized
                in _normalize(
                    clause_title
                )
            ):
                occurrence_score += 2.0

            best_sentence_score = 0.0

            for sentence in sentences:
                if (
                    normalized
                    not in _normalize(
                        sentence
                    )
                ):
                    continue

                best_sentence_score = max(
                    best_sentence_score,
                    _sentence_score(
                        question=question,
                        sentence=sentence,
                        answer_type=answer_type,
                        source_index=source_index,
                    ),
                )

            occurrence_score += (
                best_sentence_score
            )

            occurrence_score += (
                _candidate_query_alignment_score(
                    candidate,
                    query_variants,
                )
            )

            occurrence_score += (
                _candidate_local_context_score(
                    question,
                    combined_text,
                    candidate,
                )
            )

            if answer_type == "PROSEDÜR":
                occurrence_score += (
                    _procedure_specificity_score(
                        candidate,
                        query_variants,
                    )
                )

            # ---------------------------------------------
            # MESAJ YÖNÜ / İSTEK ÖNCELİKLENDİRMESİ
            # ---------------------------------------------
            if answer_type == "MESAJ":
                q_lower = question.casefold()
                cand_lower = candidate.casefold()
                if any(k in q_lower for k in ("başlat", "istek", "gönder", "talep", "establish", "initiate")):
                    if "request" in cand_lower:
                        occurrence_score += 8.0
                    elif any(k in cand_lower for k in ("accept", "reject", "response", "complete")):
                        occurrence_score -= 8.0

            if (
                answer_type
                == "ARAYÜZ / REFERANS NOKTASI"
            ):
                occurrence_score += (
                    _reference_point_relation_score(
                        candidate,
                        combined_text,
                        question,
                    )
                )

            if (
                answer_type
                == "NETWORK FUNCTION"
            ):
                occurrence_score += (
                    _network_function_relation_score(
                        candidate,
                        combined_text,
                        question,
                    )
                )

            if (
                answer_type
                == "ARAYÜZ / REFERANS NOKTASI"
                and re.fullmatch(
                    r"[A-Za-z]{1,5}\d+[A-Za-z]?",
                    candidate,
                )
            ):
                occurrence_score += 6.0

            if (
                answer_type == "PROTOKOL"
                and _is_acronym(
                    candidate
                )
            ):
                occurrence_score += 6.0

            if (
                answer_type
                == "NETWORK FUNCTION"
                and _is_acronym(
                    candidate
                )
            ):
                occurrence_score += 5.0

            occurrence_score -= (
                _subject_echo_penalty(
                    candidate,
                    question,
                    answer_type,
                )
            )

            strong_evidence = (
                _is_strong_candidate(
                    candidate,
                    combined_text,
                    question,
                    answer_type,
                )
            )

            existing = (
                candidate_scores.get(
                    normalized
                )
            )

            if existing is None:
                candidate_scores[
                    normalized
                ] = {
                    "value": candidate,
                    "score": occurrence_score,
                    "occurrences": 1,
                    "strong_evidence": (
                        strong_evidence
                    ),
                }

            else:
                existing[
                    "score"
                ] = max(
                    float(
                        existing[
                            "score"
                        ]
                    ),
                    occurrence_score,
                )

                existing[
                    "score"
                ] += 0.75

                existing[
                    "occurrences"
                ] += 1

                existing[
                    "strong_evidence"
                ] = (
                    bool(
                        existing.get(
                            "strong_evidence"
                        )
                    )
                    or strong_evidence
                )

    # -----------------------------------------------------
    # DOCUMENT RELATIONS
    # -----------------------------------------------------

    if answer_type == (
        "STANDART / DOKÜMAN"
    ):
        _add_referenced_document_candidates(
            candidate_scores,
            chunks,
            question,
        )

        _apply_document_relation_bonuses(
            candidate_scores,
            chunks,
        )

        for candidate_data in (
            candidate_scores.values()
        ):
            candidate_data[
                "score"
            ] += (
                _document_format_alignment_score(
                    question,
                    str(
                        candidate_data.get(
                            "value",
                            "",
                        )
                    ),
                )
            )

    # -----------------------------------------------------
    # SUPPORTING FACTS
    # -----------------------------------------------------

    supporting_sentences.sort(
        key=lambda item: (
            item[
                "score"
            ]
        ),
        reverse=True,
    )

    supporting_facts: list[
        dict[str, Any]
    ] = []

    seen_fact_texts: set[str] = set()

    for item in supporting_sentences:
        normalized_text = _normalize(
            item[
                "text"
            ]
        )

        if (
            normalized_text
            in seen_fact_texts
        ):
            continue

        seen_fact_texts.add(
            normalized_text
        )

        supporting_facts.append(
            item
        )

        if (
            len(
                supporting_facts
            )
            >= MAX_SUPPORTING_FACTS
        ):
            break

    # -----------------------------------------------------
    # RANKING
    # -----------------------------------------------------

    ranked_candidates = sorted(
        candidate_scores.values(),
        key=lambda item: (
            float(
                item.get(
                    "score",
                    0.0,
                )
            ),
            int(
                item.get(
                    "occurrences",
                    0,
                )
            ),
        ),
        reverse=True,
    )

    primary_answer = ""
    confidence = "low"

    if ranked_candidates:
        top = ranked_candidates[
            0
        ]

        top_score = float(
            top[
                "score"
            ]
        )

        second_score = (
            float(
                ranked_candidates[
                    1
                ][
                    "score"
                ]
            )
            if len(
                ranked_candidates
            ) > 1
            else 0.0
        )

        margin = (
            top_score
            - second_score
        )

        top_occurrences = int(
            top.get(
                "occurrences",
                0,
            )
        )

        second_occurrences = (
            int(
                ranked_candidates[
                    1
                ].get(
                    "occurrences",
                    0,
                )
            )
            if len(
                ranked_candidates
            ) > 1
            else 0
        )

        document_occurrence_win = (
            answer_type
            == "STANDART / DOKÜMAN"
            and abs(
                margin
            ) < 0.001
            and (
                top_occurrences
                >= second_occurrences + 2
            )
        )

        risky_types = {
            "ARAYÜZ / REFERANS NOKTASI",
            "PROTOKOL",
            "NETWORK FUNCTION",
            "DEĞER / LİMİT",
            "STANDART / DOKÜMAN",
            "MESAJ",
        }

        strong_enough = (
            bool(
                top.get(
                    "strong_evidence"
                )
            )
            if (
                answer_type
                in risky_types
            )
            else True
        )

        if (
            top_score >= 7.0
            and (
                margin >= 1.0
                or document_occurrence_win
            )
            and strong_enough
        ):
            primary_answer = str(
                top[
                    "value"
                ]
            )

            confidence = "high"

        elif (
            top_score >= 4.0
            and strong_enough
        ):
            primary_answer = str(
                top[
                    "value"
                ]
            )

            confidence = "medium"

    return {
        "answer_type": answer_type,
        "primary_answer": primary_answer,
        "confidence": confidence,

        "candidate_answers": [
            {
                "value": item[
                    "value"
                ],
                "score": round(
                    float(
                        item[
                            "score"
                        ]
                    ),
                    4,
                ),
                "occurrences": item[
                    "occurrences"
                ],
            }
            for item in (
                ranked_candidates[
                    :5
                ]
            )
        ],

        "supporting_facts": [
            {
                "text": item[
                    "text"
                ],
                "code": item[
                    "code"
                ],
                "clause": item[
                    "clause"
                ],
                "score": round(
                    float(
                        item[
                            "score"
                        ]
                    ),
                    4,
                ),
            }
            for item in supporting_facts
        ],
    }


# =========================================================
# GENERATOR GUIDANCE
# =========================================================

def build_composer_guidance(
    composition: dict[str, Any],
) -> str:
    answer_type = str(
        composition.get(
            "answer_type",
            "GENEL TEKNİK BİLGİ",
        )
    )

    primary_answer = str(
        composition.get(
            "primary_answer",
            "",
        )
    ).strip()

    confidence = str(
        composition.get(
            "confidence",
            "low",
        )
    )

    supporting_facts = (
        composition.get(
            "supporting_facts",
            []
        )
    )

    lines = [
        (
            "BEKLENEN CEVAP TÜRÜ: "
            f"{answer_type}"
        ),
        (
            "COMPOSER GÜVENİ: "
            f"{confidence}"
        ),
    ]

    if primary_answer:
        lines.append(
            (
                "KAYNAKTAN ÇIKARILAN "
                "ANA CEVAP: "
                f"{primary_answer}"
            )
        )

    else:
        lines.append(
            (
                "KAYNAKTAN ÇIKARILAN "
                "ANA CEVAP: BELİRSİZ"
            )
        )

    if supporting_facts:
        lines.append(
            (
                "DOĞRUDAN DESTEKLEYİCİ "
                "KAYNAK CÜMLELERİ:"
            )
        )

        for fact in supporting_facts:
            lines.append(
                "- "
                f"[{fact.get('code')} | "
                f"{fact.get('clause')}] "
                f"{fact.get('text')}"
            )

    return "\n".join(
        lines
    )