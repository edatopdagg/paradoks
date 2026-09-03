from __future__ import annotations

from io import BytesIO
import re

from pypdf import PdfReader

from v3_fetcher import _read_pdf


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


def _read_with_pypdf(
    raw_bytes: bytes,
) -> tuple[
    str,
    tuple[str, ...],
]:

    reader = PdfReader(
        BytesIO(
            raw_bytes
        )
    )

    pages = []

    for page in reader.pages:

        try:
            text = (
                page.extract_text()
                or ""
            )

        except Exception:
            text = ""

        pages.append(
            text
        )

    document_text = (
        "\n\n".join(
            (
                f"[[PAGE:{index}]]\n"
                f"{text}"
            )
            for index, text
            in enumerate(
                pages,
                start=1,
            )
        )
    )

    return (
        document_text,
        tuple(pages),
    )


def read_priority_pdf(
    raw_bytes: bytes,
):
    """
    Normal V3 extractor primary'dir.

    Eğer PDF karakter haritası yüzünden
    (cid:123) biçiminde bozuk metin
    üretiyorsa pypdf alternatif extractor
    denenir ve daha temiz sonuç seçilir.
    """

    (
        primary_text,
        primary_pages,
    ) = _read_pdf(
        raw_bytes
    )

    primary_cid = (
        _cid_count(
            primary_text
        )
    )

    # Normal belgelerde ekstra extraction
    # maliyeti oluşturma.
    if primary_cid < 20:

        return (
            primary_text,
            primary_pages,
            {
                "extractor": (
                    "v3_fetcher"
                ),
                "primary_cid": (
                    primary_cid
                ),
                "alternate_cid": None,
            },
        )

    try:

        (
            alternate_text,
            alternate_pages,
        ) = _read_with_pypdf(
            raw_bytes
        )

    except Exception:

        return (
            primary_text,
            primary_pages,
            {
                "extractor": (
                    "v3_fetcher"
                ),
                "primary_cid": (
                    primary_cid
                ),
                "alternate_cid": None,
            },
        )

    alternate_cid = (
        _cid_count(
            alternate_text
        )
    )

    # Alternatif gerçekten daha temizse seç.
    if (
        len(
            alternate_text.strip()
        ) >= 500
        and alternate_cid
        < primary_cid
    ):

        return (
            alternate_text,
            alternate_pages,
            {
                "extractor": "pypdf",
                "primary_cid": (
                    primary_cid
                ),
                "alternate_cid": (
                    alternate_cid
                ),
            },
        )

    return (
        primary_text,
        primary_pages,
        {
            "extractor": (
                "v3_fetcher"
            ),
            "primary_cid": (
                primary_cid
            ),
            "alternate_cid": (
                alternate_cid
            ),
        },
    )
