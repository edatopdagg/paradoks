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


_RFC_ENTRY = re.compile(
    r"\[\s*RFC\s*0*(?P<number>\d{3,5})\s*\]"
    r"(?P<body>.*?)(?=\[\s*[A-Z][A-Z0-9-]*\s*\]|\Z)",
    re.IGNORECASE | re.DOTALL,
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


def _ietf_sections(text: str) -> list[tuple[str, str]]:
    """Return the actual (last) normative/informative RFC bibliography sections."""

    normative = _last_heading(text, "Normative References")
    informative = _last_heading(text, "Informative References")
    sections: list[tuple[str, str]] = []

    if normative:
        end = informative.start() if informative and informative.start() > normative.end() else len(text)
        sections.append(("normative", text[normative.end() : end]))

    if informative:
        tail = text[informative.end() :]
        end_match = re.search(
            r"(?im)^\s*(?:Editor(?:'s|s)? Address|Authors?' Addresses?|Full Copyright Statement)\s*$",
            tail,
        )
        sections.append(("informative", tail[: end_match.start()] if end_match else tail))

    # Some RFC renderings omit the headings. Parsing the whole document is a
    # useful fallback, but the relationship kind is then deliberately unknown.
    if not sections:
        sections.append(("unspecified", text))

    return sections


def _parse_ietf(text: str) -> list[V3Reference]:
    discovered: list[V3Reference] = []

    for reference_kind, section in _ietf_sections(text):
        for match in _RFC_ENTRY.finditer(section):
            number = str(int(match.group("number")))
            body = _clean_space(match.group("body"))
            title_match = _QUOTED_TITLE.search(body)
            discovered.append(
                V3Reference(
                    raw_text=_clean_space(match.group(0)),
                    org="IETF",
                    code=number,
                    title=_clean_space(title_match.group("title")) if title_match else "",
                    reference_kind=reference_kind,
                )
            )

    return _deduplicate(discovered)


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

