"""Reference parsing and identity normalization for the V3 document graph."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable, Optional

from reference_parser import parse_references_section


@dataclass(frozen=True)
class V3Reference:
    """A graph edge discovered in a document's references section."""

    raw_text: str
    org: str
    code: str
    title: str = ""
    ref_number: Optional[int] = None
    reference_kind: str = "unspecified"



_IETF_LABEL_PATTERN = (
    r"(?:"
    r"RFC\s*[- ]?\s*\d{3,5}"
    r"|"
    r"[A-Z][A-Z0-9._-]*"
    r")"
)

_IETF_ENTRY = re.compile(
    rf"\[\s*"
    rf"(?P<label>{_IETF_LABEL_PATTERN})"
    rf"\s*\]"
    rf"(?P<body>.*?)"
    rf"(?="
    rf"\[\s*{_IETF_LABEL_PATTERN}\s*\]"
    rf"|\Z"
    rf")",
    re.IGNORECASE | re.DOTALL,
)

_RFC_LABEL = re.compile(
    r"^\s*RFC\s*[- ]?\s*"
    r"0*(?P<number>\d{3,5})"
    r"\s*$",
    re.IGNORECASE,
)

_RFC_BODY = re.compile(
    r"\bRFC\s*[- ]?\s*"
    r"0*(?P<number>\d{3,5})"
    r"\b",
    re.IGNORECASE,
)

_QUOTED_TITLE = re.compile(r'["“](?P<title>[^"”]+)["”]')
_ETSI_CODE = re.compile(r"^(?P<type>TS|TR|EN)\s+(?P<number>\d{3})\s?(?P<suffix>\d{3})$", re.IGNORECASE)


def _clean_space(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("\xa0", " ").replace("\u200b", "")).strip()


def _last_heading(text: str, heading: str) -> Optional[re.Match[str]]:
    matches = list(
        re.finditer(
            rf"(?im)^\s*{re.escape(heading)}\s*$",
            text,
        )
    )
    return matches[-1] if matches else None



def _ietf_sections(
    text: str,
) -> list[tuple[str, str, bool]]:
    """
    IETF bibliyografya bölümlerini döndürür.

    Tuple:
        (
            reference_kind,
            section_text,
            allow_symbolic_labels,
        )

    Modern RFC:
        Normative References
        Informative References

    Legacy RFC:
        References

    Hiçbiri yoksa bütün belge fallback olarak
    kullanılır; ancak bu durumda sembolik label
    -> gövdedeki RFC dönüşümü kapalıdır.
    Böylece örneğin:
        [Page 1] RFC 2119
    yanlış bibliography edge üretmez.
    """

    normative = _last_heading(
        text,
        "Normative References",
    )

    informative = _last_heading(
        text,
        "Informative References",
    )

    generic = _last_heading(
        text,
        "References",
    )

    sections: list[
        tuple[str, str, bool]
    ] = []

    if normative:

        end = (
            informative.start()
            if (
                informative
                and informative.start()
                > normative.end()
            )
            else len(text)
        )

        section = text[
            normative.end():
            end
        ]

        sections.append(
            (
                "normative",
                section,
                True,
            )
        )

    if informative:

        tail = text[
            informative.end():
        ]

        end_match = re.search(
            (
                r"(?im)^\s*"
                r"(?:"
                r"Editor(?:'s|s)? Address"
                r"|Authors?' Addresses?"
                r"|Full Copyright Statement"
                r")"
                r"\s*$"
            ),
            tail,
        )

        section = (
            tail[
                :end_match.start()
            ]
            if end_match
            else tail
        )

        sections.append(
            (
                "informative",
                section,
                True,
            )
        )

    # Legacy RFC'lerde yalnız:
    #
    #     References
    #
    # başlığı bulunabilir.
    #
    # Normative / Informative varsa generic olanı
    # ayrıca işleme; aynı bibliography'yi iki kez
    # parse etme.
    if (
        not sections
        and generic
    ):

        tail = text[
            generic.end():
        ]

        end_match = re.search(
            (
                r"(?im)^\s*"
                r"(?:"
                r"Changes Since"
                r"(?:\s+RFC[-\s]?\d+)?"
                r"|Editor(?:'s|s)? Address"
                r"|Authors?' Addresses?"
                r"|Full Copyright Statement"
                r")"
                r"\s*$"
            ),
            tail,
        )

        section = (
            tail[
                :end_match.start()
            ]
            if end_match
            else tail
        )

        sections.append(
            (
                "unspecified",
                section,
                True,
            )
        )

    # Bazı RFC render'larında bibliography heading
    # bulunmayabilir. Eski davranışı koruyoruz.
    #
    # Ancak bütün belge fallback'inde symbolic label
    # çözümleme kapalıdır. Yalnız doğrudan RFC label:
    #
    #     [RFC2119]
    #     [RFC-2119]
    #
    # kabul edilir.
    if not sections:

        sections.append(
            (
                "unspecified",
                text,
                False,
            )
        )

    return sections


def _rfc_number_from_entry(
    *,
    label: str,
    body: str,
    allow_symbolic_label: bool,
) -> str | None:
    """
    Bibliography entry'nin RFC kimliğini çözer.

    Desteklenen örnekler:

        [RFC2119]
        [RFC-2401]
        [RFC 2401]

    Legacy symbolic label:

        [ICMPv6]
        ... RFC 2463 ...

        [ADDRARCH]
        ... RFC 2373 ...

    Symbolic label çözümleme yalnız gerçek
    bibliography section içinde yapılır.
    """

    clean_label = _clean_space(
        label
    )

    label_match = (
        _RFC_LABEL.fullmatch(
            clean_label
        )
    )

    if label_match:

        return str(
            int(
                label_match.group(
                    "number"
                )
            )
        )

    if not allow_symbolic_label:
        return None

    body_match = _RFC_BODY.search(
        body
    )

    if body_match is None:
        return None

    return str(
        int(
            body_match.group(
                "number"
            )
        )
    )


def _parse_ietf(
    text: str,
) -> list[V3Reference]:

    discovered: list[
        V3Reference
    ] = []

    for (
        reference_kind,
        section,
        allow_symbolic_labels,
    ) in _ietf_sections(
        text
    ):

        for match in (
            _IETF_ENTRY.finditer(
                section
            )
        ):

            label = match.group(
                "label"
            )

            body = _clean_space(
                match.group(
                    "body"
                )
            )

            number = (
                _rfc_number_from_entry(
                    label=label,
                    body=body,
                    allow_symbolic_label=(
                        allow_symbolic_labels
                    ),
                )
            )

            if number is None:
                continue

            title_match = (
                _QUOTED_TITLE.search(
                    body
                )
            )

            discovered.append(
                V3Reference(
                    raw_text=(
                        _clean_space(
                            match.group(0)
                        )
                    ),
                    org="IETF",
                    code=number,
                    title=(
                        _clean_space(
                            title_match.group(
                                "title"
                            )
                        )
                        if title_match
                        else ""
                    ),
                    reference_kind=(
                        reference_kind
                    ),
                )
            )

    return _deduplicate(
        discovered
    )

def _normalize_etsi_identity(org: str, code: str) -> tuple[str, str]:
    """Map ETSI publication aliases such as TS 123 041 to 3GPP TS 23.041."""

    if org != "ETSI":
        return org, code

    match = _ETSI_CODE.fullmatch(_clean_space(code))
    if not match:
        return org, _clean_space(code)

    publication_series = int(match.group("number"))
    # ETSI publishes 3GPP specifications as 12x/13x/14x/15x series aliases.
    # Native ETSI documents such as TS 102 182 must remain ETSI identities.
    if 121 <= publication_series <= 159:
        three_gpp_series = publication_series - 100
        normalized = f"{match.group('type').upper()} {three_gpp_series:02d}.{match.group('suffix')}"
        return "3GPP", normalized

    return org, f"{match.group('type').upper()} {match.group('number')} {match.group('suffix')}"


def _parse_telecom(text: str) -> list[V3Reference]:
    parsed: list[V3Reference] = []
    for reference in parse_references_section(text):
        target_org, target_code = _normalize_etsi_identity(reference.org, reference.code)
        parsed.append(
            V3Reference(
                raw_text=reference.raw_text,
                org=target_org,
                code=target_code,
                title=reference.title,
                ref_number=reference.ref_number,
                reference_kind="unspecified",
            )
        )
    return _deduplicate(parsed)


def _deduplicate(references: Iterable[V3Reference]) -> list[V3Reference]:
    """Deduplicate target identities; normative relationships take precedence."""

    result: list[V3Reference] = []
    positions: dict[tuple[str, str], int] = {}
    priority = {"unspecified": 0, "informative": 1, "normative": 2}

    for reference in references:
        key = (reference.org.upper(), reference.code.upper())
        existing_position = positions.get(key)
        if existing_position is None:
            positions[key] = len(result)
            result.append(reference)
            continue

        existing = result[existing_position]
        if priority.get(reference.reference_kind, 0) > priority.get(existing.reference_kind, 0):
            result[existing_position] = reference

    return result


def parse_v3_references(org: str, document_text: str) -> list[V3Reference]:
    """Parse outgoing reference edges for a supported source organization."""

    if org.strip().upper() == "IETF":
        return _parse_ietf(document_text)
    return _parse_telecom(document_text)

