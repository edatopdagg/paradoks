import re
from typing import Any


_REFERENCE_POINT_PATTERN = re.compile(
    r"\b(N\d{1,3})\b",
    flags=re.IGNORECASE,
)

_SERVICE_EXTENSION_PATTERN = re.compile(
    (
        r"in\s+the\s+case\s+of\s+"
        r"([A-Za-z0-9][A-Za-z0-9 /_-]{0,60}?)"
        r"\s+Service\b"
    ),
    flags=re.IGNORECASE,
)


def _normalize(
    value: str,
) -> str:
    return re.sub(
        r"\s+",
        " ",
        (value or "").strip().casefold(),
    )


def _tokens(
    value: str,
) -> set[str]:
    return {
        token
        for token in re.findall(
            r"[a-z0-9]+",
            (value or "").casefold(),
        )
        if len(token) >= 2
    }


def _text_similarity(
    left: str,
    right: str,
) -> float:
    left_tokens = _tokens(left)
    right_tokens = _tokens(right)

    if (
        not left_tokens
        or not right_tokens
    ):
        return 0.0

    intersection = len(
        left_tokens & right_tokens
    )

    union = len(
        left_tokens | right_tokens
    )

    if not union:
        return 0.0

    return intersection / union


def _numeric_rfc(
    result: dict[str, Any],
) -> int | None:
    metadata = (
        result.get(
            "metadata",
            {},
        )
        or {}
    )

    if (
        str(
            metadata.get(
                "org",
                "",
            )
            or ""
        ).casefold()
        != "ietf"
    ):
        return None

    code = str(
        metadata.get(
            "code",
            "",
        )
        or ""
    ).strip()

    if not code.isdigit():
        return None

    return int(code)


def _drop_equivalent_old_ietf_revisions(
    results: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Ayn? teknik b?l?m? ta??yan iki IETF RFC aday?
    neredeyse ayn? i?erikteyse daha yeni RFC'yi tutar.

    RFC numaras?n? tek ba??na "daha g?ncel" saymaz.
    ?u ?? ko?ul birlikte gerekir:

    - ikisi de IETF RFC;
    - clause title ayn?;
    - i?erik y?ksek oranda e?de?er.

    B?ylece RFC 7540 / Streams and Multiplexing ile
    RFC 9113 / Streams and Multiplexing gibi ger?ek
    revizyon ?iftlerinde eski duplicate ??kar?l?r.
    """

    keep = [
        True
        for _ in results
    ]

    for left_index in range(
        len(results)
    ):
        if not keep[left_index]:
            continue

        left = results[
            left_index
        ]

        left_rfc = _numeric_rfc(
            left
        )

        if left_rfc is None:
            continue

        left_metadata = (
            left.get(
                "metadata",
                {},
            )
            or {}
        )

        left_title = _normalize(
            str(
                left_metadata.get(
                    "clause_title",
                    "",
                )
                or ""
            )
        )

        if not left_title:
            continue

        left_text = str(
            left.get(
                "text",
                "",
            )
            or ""
        )

        for right_index in range(
            left_index + 1,
            len(results),
        ):
            if not keep[
                right_index
            ]:
                continue

            right = results[
                right_index
            ]

            right_rfc = _numeric_rfc(
                right
            )

            if right_rfc is None:
                continue

            right_metadata = (
                right.get(
                    "metadata",
                    {},
                )
                or {}
            )

            right_title = _normalize(
                str(
                    right_metadata.get(
                        "clause_title",
                        "",
                    )
                    or ""
                )
            )

            if (
                not right_title
                or left_title
                != right_title
            ):
                continue

            right_text = str(
                right.get(
                    "text",
                    "",
                )
                or ""
            )

            similarity = (
                _text_similarity(
                    left_text,
                    right_text,
                )
            )

            if similarity < 0.50:
                continue

            if left_rfc < right_rfc:
                keep[
                    left_index
                ] = False
                break

            if right_rfc < left_rfc:
                keep[
                    right_index
                ] = False

    return [
        result
        for index, result
        in enumerate(results)
        if keep[index]
    ]


def _question_reference_point(
    question: str,
) -> str:
    match = (
        _REFERENCE_POINT_PATTERN
        .search(
            question or ""
        )
    )

    if not match:
        return ""

    return (
        match.group(1)
        .upper()
    )


def _service_labels(
    results: list[dict[str, Any]],
) -> list[str]:
    labels: list[str] = []

    for result in results:
        text = str(
            result.get(
                "text",
                "",
            )
            or ""
        )

        for match in (
            _SERVICE_EXTENSION_PATTERN
            .finditer(text)
        ):
            label = _normalize(
                match.group(1)
            )

            if (
                label
                and label not in labels
            ):
                labels.append(
                    label
                )

    return labels


def _question_mentions_service(
    question: str,
    labels: list[str],
) -> bool:
    question_tokens = _tokens(
        question
    )

    for label in labels:
        label_tokens = _tokens(
            label
        )

        if (
            label_tokens
            and label_tokens.issubset(
                question_tokens
            )
        ):
            return True

    return False


def _reference_point_bonus(
    *,
    question: str,
    result: dict[str, Any],
    service_specific_question: bool,
) -> float:
    reference_point = (
        _question_reference_point(
            question
        )
    )

    if not reference_point:
        return 0.0

    text = str(
        result.get(
            "text",
            "",
        )
        or ""
    )

    bonus = 0.0

    direct_definition = re.search(
        (
            rf"\b{re.escape(reference_point)}"
            r"\s*:\s*"
            r"Reference\s+point\s+between\b"
        ),
        text,
        flags=re.IGNORECASE,
    )

    # Genel N2/N3/... sorusunda kanonik
    # "N2: Reference point between..." tan?m?n?
    # service-specific extension'dan ?ne al.
    if (
        direct_definition
        and not service_specific_question
    ):
        bonus += 2.0

    normalized_text = _normalize(
        text
    )

    is_extension = (
        "in addition to the relevant functions defined in"
        in normalized_text
    )

    if (
        is_extension
        and not service_specific_question
    ):
        bonus -= 1.0

    return bonus



def _drop_service_extensions_for_generic_reference_question(
    *,
    question: str,
    results: list[dict[str, Any]],
    service_specific_question: bool,
) -> list[dict[str, Any]]:
    """
    Genel N1/N2/N3/... sorusunda kanonik direct definition
    bulunduysa service-specific extension chunk'lar?n? ??kar.

    ?rnek:

      generic:
        N2 referans noktas? hangi fonksiyonlar aras?ndad?r?

      canonical:
        N2: Reference point between the (R)AN and the AMF.

      extension:
        In addition to the relevant functions defined in
        TS 23.501 for N2, in the case of A2X Service...

    Generic soruda extension LLM promptuna girmez.

    Kullan?c? a??k?a A2X Service gibi ?zel servisi sorarsa
    extension korunur.
    """

    if (
        not results
        or service_specific_question
    ):
        return results

    reference_point = (
        _question_reference_point(
            question
        )
    )

    if not reference_point:
        return results

    direct_pattern = re.compile(
        (
            rf"\b{re.escape(reference_point)}"
            r"\s*:\s*"
            r"Reference\s+point\s+between\b"
        ),
        flags=re.IGNORECASE,
    )

    canonical_found = any(
        direct_pattern.search(
            str(
                result.get(
                    "text",
                    "",
                )
                or ""
            )
        )
        for result in results
    )

    if not canonical_found:
        return results

    filtered: list[
        dict[str, Any]
    ] = []

    for result in results:

        candidate_text = str(
            result.get(
                "text",
                "",
            )
            or ""
        )

        normalized_text = (
            _normalize(
                candidate_text
            )
        )

        contains_same_reference = bool(
            re.search(
                (
                    rf"\b"
                    rf"{re.escape(reference_point)}"
                    rf"\b"
                ),
                candidate_text,
                flags=re.IGNORECASE,
            )
        )

        is_service_extension = (
            contains_same_reference
            and (
                "in addition to the relevant functions defined in"
                in normalized_text
            )
            and (
                _SERVICE_EXTENSION_PATTERN.search(
                    candidate_text
                )
                is not None
            )
        )

        if is_service_extension:
            continue

        filtered.append(
            result
        )

    return filtered or results


def prioritize_evidence(
    question: str,
    results: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    CrossEncoder skorunu ??pe atmadan final evidence
    s?ralamas?na kaynak-semantik bilgisi ekler.

    Kurallar:
    1. E?de?er IETF revizyonlar?nda eski duplicate'i ??kar.
    2. Genel Nxx sorular?nda kanonik direct definition'?
       service-specific extension'?n ?n?ne al.
    3. Kullan?c? ?zel servisi a??k?a soruyorsa extension
       aday?n? cezaland?rma.
    """

    if not results:
        return []

    filtered = (
        _drop_equivalent_old_ietf_revisions(
            list(results)
        )
    )

    labels = _service_labels(
        filtered
    )

    service_specific_question = (
        _question_mentions_service(
            question,
            labels,
        )
    )

    filtered = (
        _drop_service_extensions_for_generic_reference_question(
            question=question,
            results=filtered,
            service_specific_question=(
                service_specific_question
            ),
        )
    )

    prioritized: list[
        tuple[
            float,
            int,
            dict[str, Any],
        ]
    ] = []

    for index, result in enumerate(
        filtered
    ):
        copy = dict(
            result
        )

        rerank_score = float(
            result.get(
                "rerank_score",
                0.0,
            )
            or 0.0
        )

        bonus = (
            _reference_point_bonus(
                question=question,
                result=result,
                service_specific_question=(
                    service_specific_question
                ),
            )
        )

        final_score = (
            rerank_score
            + bonus
        )

        copy[
            "evidence_priority_bonus"
        ] = bonus

        copy[
            "evidence_priority_score"
        ] = final_score

        prioritized.append(
            (
                final_score,
                -index,
                copy,
            )
        )

    prioritized.sort(
        key=lambda item: (
            item[0],
            item[1],
        ),
        reverse=True,
    )

    return [
        item[2]
        for item in prioritized
    ]
