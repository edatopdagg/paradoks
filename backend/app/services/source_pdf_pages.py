"""Return only catalog-authorized pages of an original standard PDF.

Page indexes in the catalog are 1-based and match the PDF viewer page numbers.
The source PDF on disk is never modified.
"""
from pathlib import Path

import pymupdf

MAX_CLAUSE_PAGES = 128
MAX_PDF_BYTES = 60 * 1024 * 1024


def extract_clause_pdf_pages(
    source_pdf: str | Path,
    page_start: int | str | None,
    page_end: int | str | None,
) -> bytes:
    try:
        if isinstance(page_start, bool) or isinstance(page_end, bool):
            raise ValueError("Boolean page numbers are invalid")
        start = int(page_start)  # type: ignore[arg-type]
        end = int(page_end)  # type: ignore[arg-type]
    except (TypeError, ValueError) as exc:
        raise ValueError("Catalog PDF page range is missing or invalid") from exc

    if start < 1 or end < start or end - start + 1 > MAX_CLAUSE_PAGES:
        raise ValueError("Catalog PDF page range is outside the supported limits")

    with pymupdf.open(str(source_pdf)) as original:
        if end > original.page_count:
            raise ValueError("Catalog page range exceeds the original PDF")
        with pymupdf.open() as excerpt:
            excerpt.insert_pdf(
                original,
                from_page=start - 1,
                to_page=end - 1,
                links=True,
                annots=True,
            )
            data = excerpt.tobytes(garbage=3, deflate=True)

    if len(data) > MAX_PDF_BYTES or not data.startswith(b"%PDF-"):
        raise ValueError("Selected PDF pages could not be safely returned")
    return data
