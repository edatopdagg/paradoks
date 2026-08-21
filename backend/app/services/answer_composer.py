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
    r"(?:UE|network)[-\s]+initiated"
    r"\s+"
    r"(?:[A-Za-z0-9/\-]+\s+){0,4}"
    r"procedure"
    r")"
    r"|"
    r"(?:"
    r"[A-Za-z0-9/\-]+"
    r"\s+procedure"
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
        r"([A-Z][A-Z0-9\-]{1,12})"
        r"\s+and\s+"
        r"(?:the\s+)?"
        r"([A-Z][A-Z0-9\-]{1,12})"
        r"\b",
        flags=re.IGNORECASE,
    ),
    re.compile(
        r"\bReference\s+point\s+between\s+"
        r"(?:the\s+)?"
        r"([A-Z][A-Z0-9\-]{1,12})"
        r"\s+and\s+"
        r"(?:the\s+)?"
        r"([A-Z][A-Z0-9\-]{1,12})"
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


# =========================================================
# GENERIC CANDIDATES
# =========================================================

GENERIC_CANDIDATES = {
    "between",

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
    tokens = {
        token.casefold()
        for token in WORD_PATTERN.findall(
            value or ""
        )
    }

    return {
        token
        for token in tokens
        if (
            len(token) >= 2
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


# =========================================================
# QUESTION ENTITY HELPERS
# =========================================================

def _question_acronyms(
    question: str,
) -> set[str]:
    """
    Soruda açıkça geçen teknik acronym'leri çıkarır.

    Örnek:

        "AMF ile SMF arasındaki..."
            -> {"AMF", "SMF"}

    5G / 5GS yalnızca sistem bağlamıdır ve
    ilişki ucu olarak kullanılmaz.
    """

    acronyms = {
        item.upper()
        for item in ACRONYM_PATTERN.findall(
            question or ""
        )
    }

    return {
        item
        for item in acronyms
        if item not in {
            "5G",
            "5GS",
        }
    }


# =========================================================
# REFERENCE POINT RELATION
# =========================================================

def _reference_point_relation_score(
    candidate: str,
    text: str,
    question: str,
) -> float:
    """
    Nxx adayını sorudaki iki teknik uçla ilişkilendirir.

    Örnek kaynak:

        N11: Reference point between the AMF and the SMF

    Örnek soru:

        AMF ile SMF arasındaki referans noktası hangisidir?

    Bu durumda yalnızca N11 yüksek ilişki bonusu alır.
    """

    candidate_norm = (
        candidate
        or ""
    ).strip().casefold()

    question_entities = (
        _question_acronyms(
            question
        )
    )

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
                left.upper(),
                right.upper(),
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


# =========================================================
# NETWORK FUNCTION RELATION
# =========================================================

def _network_function_anchor_tokens(
    question: str,
) -> set[str]:
    """
    Network Function sorusunun gerçek konu kelimelerini
    çıkarır.

    Örnek:

        5GS registration management işlemlerini
        hangi network function yürütür?

    anchor:
        registration
        management

    "network" ve "function" cevap türünü anlatır,
    sorunun konusunu anlatmaz; bu yüzden çıkarılır.
    """

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
    """
    Sorunun ana teknik kavramını içeren cümlelerin
    bir önceki ve bir sonraki cümlesini de kapsayan
    küçük bağlam pencereleri üretir.

    Böylece:

        Registration Management ...
        The AMF ...

    gibi iki cümleye bölünmüş ilişkiler de yakalanır.
    """

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
    """
    Bir acronym'in kaynakta hangi uzun ismin
    kısaltması olarak tanımlandığını inceler.

    Örnek:

        Access and Mobility Management Function (AMF)
            -> pozitif

        Short Message Service (SMS)
            -> negatif

    Böylece her büyük harfli ifade NF kabul edilmez.
    """

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
    """
    NF adayını sorunun teknik konusuyla ilişkilendirir.

    Sadece acronym olmasına puan verilmez.
    Adayın registration management gibi sorunun
    gerçek konu kelimelerinin yakınında olması gerekir.
    """

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

        # Sorumluluk / görev ilişkisi.
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
            )
        ):
            relation_score += 5.0

        # Candidate ile konu gerçekten aynı lokal bağlamda mı?
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


# =========================================================
# QUERY ALIGNMENT
# =========================================================

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


# =========================================================
# SUBJECT ECHO
# =========================================================

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


# =========================================================
# PROCEDURE SPECIFICITY
# =========================================================

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


# =========================================================
# SENTENCE SCORE
# =========================================================

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
        ):
            score += 2.5

    elif answer_type == "DEĞER / LİMİT":
        if VALUE_PATTERN.search(
            sentence
        ):
            score += 3.0

    return score


# =========================================================
# CANDIDATE EXTRACTION
# =========================================================

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
        # ---------------------------------------------
        # 1. Güçlü yapısal NF tanımları
        # ---------------------------------------------

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

        # ---------------------------------------------
        # 2. Soru konusunun geçtiği bağlam pencereleri
        # ---------------------------------------------
        #
        # Eskiden "function" kelimesi geçen herhangi bir
        # cümledeki bütün acronym'ler aday olabiliyordu.
        #
        # Bu yüzden SMS gibi servis kısaltmaları NF
        # sanılabiliyordu.
        #
        # Şimdi yalnızca sorunun konu anchor'larının
        # bulunduğu pencereler taranıyor.
        # ---------------------------------------------

        for window in _network_function_windows(
            text,
            question,
        ):
            for acronym in ACRONYM_PATTERN.findall(
                window
            ):
                if acronym in NF_ACRONYM_EXCLUDES:
                    continue

                # Generic taramada yalnızca gerçek acronym
                # biçimi kabul edilir.
                #
                # CON-005, REQ- gibi test/requirement
                # identifier'ları NF adayı olmaz.
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

                # Kaynak açıkça bunun Service / Protocol
                # vb. olduğunu söylüyorsa NF adayı yapma.
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

    # -----------------------------------------------------
    # UNIQUE
    # -----------------------------------------------------

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


# =========================================================
# STRONG EVIDENCE
# =========================================================

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


# =========================================================
# DOCUMENT HELPERS
# =========================================================

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
            f"RFC {clean_code}"
        )

    if clean_org:
        return (
            f"{clean_org} {clean_code}"
        ).strip()

    return clean_code


def _document_directness_score(
    question: str,
    text: str,
) -> float:
    """
    Bir dokümanın sorulan teknik konuyu doğrudan
    tanımlayıp tanımlamadığını puanlar.

    Örnek güçlü kanıtlar:

        This document defines version 1 of QUIC

        The present document specifies ...

        This document describes ...

    Sadece "this document defines" görülmesi yeterli
    değildir; sorunun teknik konusu da aynı kaynakta
    bulunmalıdır.
    """

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

    # -----------------------------------------------------
    # SORUNUN GERÇEK TEKNİK KONUSUNU AYIR
    # -----------------------------------------------------
    #
    # "RFC", "standart", "protocol" gibi kelimeler
    # cevap türünü anlatır.
    #
    # QUIC, HTTP/3, multicast vb. ise asıl konudur.
    # -----------------------------------------------------

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
    # DOKÜMAN KENDİ KAPSAMINI DOĞRUDAN TANIMLIYOR
    # -----------------------------------------------------

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
        score += 6.0

    # -----------------------------------------------------
    # DAHA ZAYIF AMA YİNE DOĞRUDAN DOKÜMAN İLİŞKİSİ
    # -----------------------------------------------------

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

            score = (
                5.0
                - min(
                    index,
                    3,
                )
                + directness
            )

            candidate_scores[
                normalized
            ] = {
                "value": value,
                "score": score,
                "occurrences": 1,
                "strong_evidence": (
                    directness >= 4.0
                ),
            }

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

            # Clause title bonus
            if (
                clause_title
                and normalized
                in _normalize(
                    clause_title
                )
            ):
                occurrence_score += 2.0

            # -----------------------------------------
            # BEST SENTENCE
            # -----------------------------------------

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

            # -----------------------------------------
            # QUERY ALIGNMENT
            # -----------------------------------------

            occurrence_score += (
                _candidate_query_alignment_score(
                    candidate,
                    query_variants,
                )
            )

            # -----------------------------------------
            # LOCAL CONTEXT
            # -----------------------------------------

            occurrence_score += (
                _candidate_local_context_score(
                    question,
                    combined_text,
                    candidate,
                )
            )

            # -----------------------------------------
            # PROCEDURE RELATION
            # -----------------------------------------

            if answer_type == "PROSEDÜR":
                occurrence_score += (
                    _procedure_specificity_score(
                        candidate,
                        query_variants,
                    )
                )

            # -----------------------------------------
            # REFERENCE POINT RELATION
            # -----------------------------------------

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

            # -----------------------------------------
            # NETWORK FUNCTION RELATION
            # -----------------------------------------

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

            # -----------------------------------------
            # IDENTIFIER BONUS
            # -----------------------------------------

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

            # -----------------------------------------
            # SUBJECT ECHO PENALTY
            # -----------------------------------------

            occurrence_score -= (
                _subject_echo_penalty(
                    candidate,
                    question,
                    answer_type,
                )
            )

            # -----------------------------------------
            # STRONG EVIDENCE
            # -----------------------------------------

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
        _apply_document_relation_bonuses(
            candidate_scores,
            chunks,
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
            item[
                "score"
            ]
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

        risky_types = {
            "ARAYÜZ / REFERANS NOKTASI",
            "PROTOKOL",
            "NETWORK FUNCTION",
            "DEĞER / LİMİT",
            "STANDART / DOKÜMAN",
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
            and margin >= 1.0
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