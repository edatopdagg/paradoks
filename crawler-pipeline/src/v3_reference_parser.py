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



# IETF bibliography label'ları tarihsel olarak çok
# farklı biçimlerde kullanılabiliyor:
#
#   [RFC2119]
#   [RFC-2401]
#   [ICMPv6]
#   [1]
#   [IAB-RFC1087, 1989]
#   [Reynolds-RFC1135, 1989]
#   [Eichin and Rochlis, 1989]
#
# Dolayısıyla label içeriğini dar bir whitelist ile
# sınırlamak yerine gerçek bibliography entry sınırını
# SATIR BAŞINDAKİ [ ... ] yapısıyla belirliyoruz.
#
# [Page 66] gibi RFC Editor artifact'ları bibliography
# label değildir.
_IETF_LABEL_PATTERN = (
    r"(?!Page\s+\d+\b)"
    r"[^\[\]\r\n]{1,160}"
)

_IETF_ENTRY = re.compile(
    rf"^[ \t]*"
    rf"\[[ \t\r\n]*"
    rf"(?P<label>{_IETF_LABEL_PATTERN})"
    rf"[ \t\r\n]*\]"
    rf"(?P<body>.*?)"
    rf"(?="
    rf"^[ \t]*"
    rf"\[[ \t\r\n]*"
    rf"{_IETF_LABEL_PATTERN}"
    rf"[ \t\r\n]*\]"
    rf"|\Z"
    rf")",
    re.IGNORECASE
    | re.DOTALL
    | re.MULTILINE,
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


def _last_heading(
    text: str,
    heading: str,
) -> Optional[re.Match[str]]:
    """
    RFC bibliography başlığının gerçek gövde
    içindeki son occurrence'ını döndürür.

    Desteklenen örnekler:

        Normative References

        . Normative References

        Informative References

        . Informative References

    TOC satırlarındaki trailing dot leader'ları
    özellikle eşleştirilmez; böylece gerçek body
    heading tercih edilir.
    """

    matches = list(
        re.finditer(
            (
                rf"(?im)^\s*"
                rf"(?:\.\s*)?"
                rf"{re.escape(heading)}"
                rf"\s*$"
            ),
            text,
        )
    )

    return (
        matches[-1]
        if matches
        else None
    )


def _trim_ietf_reference_section(
    section: str,
) -> str:
    """
    IETF bibliography bölümünü gerçek sonraki
    doküman bölümünde keser.

    Özellikle şu taşmayı engeller:

        Normative References
        ...
        Appendix A
        ...
        RFC 1750

    Appendix içindeki RFC ifadeleri bibliography
    referansı değildir.

    Yalnız bağımsız bölüm başlıkları eşleştirilir;
    normal paragraf içindeki "appendix" kelimesine
    dokunulmaz.
    """

    boundary = re.search(
        (
            r"(?im)^\s*"
            r"(?:\.\s*)?"
            r"(?:"
            r"Appendix(?:\s+[A-Z0-9]+)?"
            r"|Acknowledg(?:e)?ments?"
            r"|Editor(?:'s|s)? Address"
            r"|Authors?' Addresses?"
            r"|Full Copyright Statement"
            r")"
            r"\s*$"
        ),
        section,
    )

    if boundary is None:
        return section

    return section[
        :boundary.start()
    ]


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

        section = (
            _trim_ietf_reference_section(
                text[
                    normative.end():
                    end
                ]
            )
        )

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

        section = (
            _trim_ietf_reference_section(
                section
            )
        )

        section = (
            _trim_ietf_reference_section(
                section
            )
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

                # Legacy RFC extraction bazen terminal
                # heading'in section/page numarasını ayrı
                # satıra çıkarır:
                #
                #     6
                #     . Editors' Addresses
                #
                #     7
                #     . Full Copyright Statement
                #
                # Yalnız terminal heading'in hemen önündeki
                # yalın section numarasına izin veriyoruz.
                r"(?:"
                r"[1-9]\d?"
                r"(?:\.\d+)*"
                r"\.?"
                r"\s*\n\s*"
                r")?"

                # Split extraction'daki baştaki ".".
                r"(?:\.\s*)?"

                r"(?:"
                r"Changes Since"
                r"(?:\s+RFC[-\s]?\d+)?"

                # Editor's Address
                # Editors' Addresses
                # Editors Addresses
                r"|Editors?"
                r"(?:'s|')?"
                r"\s+Addresses?"

                # Author's Address
                # Authors' Addresses
                # Authors Addresses
                r"|Authors?"
                r"(?:'s|')?"
                r"\s+Addresses?"

                r"|Full Copyright Statement"
                r"|Copyright Statement"
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

    # Bazı RFC'lerde genel "References" bölümü ile
    # sonradan gelen "Normative References" / "Informative
    # References" bölümleri birlikte bulunur.
    #
    # Örnek RFC 3309:
    #
    #     6
    #     References
    #       [RFC1700]
    #       [RFC2026]
    #       [RFC2119]
    #       [RFC2960]
    #
    #     7.1
    #     Informative References
    #       [STONE]
    #
    # Typed section bulundu diye genel References bölümünü
    # kaybetmemeliyiz. Generic bölümü bir sonraki typed
    # reference heading'e kadar ayrı bir "unspecified"
    # bibliography section olarak koruyoruz.
    if sections:

        generic_matches = list(
            re.finditer(
                (
                    r"(?im)^\s*"
                    r"(?:"
                    r"\d+(?:\.\d+)*\.?\s*"
                    r")?"
                    r"\.?\s*"
                    r"References"
                    r"\s*$"
                ),
                text,
            )
        )

        typed_matches = list(
            re.finditer(
                (
                    r"(?im)^\s*"
                    r"(?:"
                    r"\d+(?:\.\d+)*\.?\s*"
                    r")?"
                    r"\.?\s*"
                    r"(?:Normative|Informative)"
                    r"\s+References"
                    r"\s*$"
                ),
                text,
            )
        )

        if (
            generic_matches
            and typed_matches
        ):

            # RFC Editor HTML render'larında TOC içinde de
            # "References" görünebildiği için son generic
            # heading'i esas alıyoruz.
            generic_match = (
                generic_matches[-1]
            )

            later_typed = [
                match
                for match in typed_matches
                if (
                    match.start()
                    > generic_match.end()
                )
            ]

            if later_typed:

                next_typed = min(
                    later_typed,
                    key=lambda match: (
                        match.start()
                    ),
                )

                generic_section = (
                    _trim_ietf_reference_section(
                        text[
                            generic_match.end():
                            next_typed.start()
                        ]
                    )
                )

                if generic_section.strip():

                    sections.insert(
                        0,
                        (
                            "unspecified",
                            generic_section,
                            True,
                        ),
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


def _strip_ietf_page_header_rfc(
    body: str,
) -> str:
    """
    RFC Editor HTML -> text dönüşümünde bibliography
    entry'lerinin arasına giren sayfa header/footer RFC
    kimliklerini temizler.

    Örnek:

        Schulzrinne, et al. Standards Track [Page 100]
        RFC 3550
        RTP July 2003

    Buradaki RFC 3550 bibliography referansı değildir;
    mevcut belgenin sayfa üstbilgisidir.

    Aynı durum:

        Leach, et al. Standards Track [Page 17]
        RFC 4122
        A UUID URN Namespace July 2005

    biçiminde de görülür.

    Yalnız [Page N] satırını hemen takip eden RFC kimlik
    satırı kaldırılır. Entry içerisindeki gerçek
    bibliyografik RFC xxxx ifadelerine dokunulmaz.
    """

    return re.sub(
        (
            r"(?im)"
            r"^[^\n]*"
            r"\[Page\s+\d+\]"
            r"[^\n]*"
            r"\n"
            r"(?:[ \t]*\n)*"
            r"[ \t]*"
            r"RFC[ \t]*:?[ \t]*"
            r"\d{3,5}"
            r"[ \t]*$"
        ),
        "",
        body,
    )


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

    searchable_body = (
        _strip_ietf_page_header_rfc(
            body
        )
    )

    body_match = _RFC_BODY.search(
        searchable_body
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


def _ietf_title_from_entry(
    *,
    raw_body: str,
    clean_body: str,
) -> str:
    """
    IETF bibliography entry başlığını çıkarır.

    Öncelik:
    1. Tırnak içindeki klasik RFC başlığı.
    2. Legacy tırnaksız kayıtlarda RFC numarasından
       hemen önceki son anlamlı satır.

    Örnek:

        [Reynolds-RFC1135, 1989]
        The Helminthiasis of the Internet,
        RFC 1135,
        ...

    -> The Helminthiasis of the Internet
    """

    quoted = _QUOTED_TITLE.search(
        clean_body
    )

    if quoted is not None:
        return _clean_space(
            quoted.group(
                "title"
            )
        )

    rfc_match = _RFC_BODY.search(
        raw_body
    )

    if rfc_match is None:
        return ""

    prefix = raw_body[
        :rfc_match.start()
    ]

    lines = [
        _clean_space(line)
        for line in prefix.splitlines()
        if _clean_space(line)
    ]

    if not lines:
        return ""

    candidate = lines[-1].strip()

    candidate = re.sub(
        r"[\s,;:.]+$",
        "",
        candidate,
    ).strip()

    return candidate


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

            raw_body = match.group(
                "body"
            )

            body = _clean_space(
                raw_body
            )

            number = (
                _rfc_number_from_entry(
                    label=label,
                    body=raw_body,
                    allow_symbolic_label=(
                        allow_symbolic_labels
                    ),
                )
            )

            if number is None:
                continue

            title = _ietf_title_from_entry(
                raw_body=raw_body,
                clean_body=body,
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
                    title=title,
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

