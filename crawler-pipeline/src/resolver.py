import os
import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from dotenv import load_dotenv

from models import Reference, ResolvedSource, DocStatus

load_dotenv()
API_KEY = os.environ.get("GOOGLE_API_KEY")
CX = os.environ.get("GOOGLE_CX")

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; standards-crawler/1.0)"}
TIMEOUT = 15


def _get(url: str) -> requests.Response | None:
    try:
        resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        if resp.status_code == 200:
            return resp
    except requests.RequestException:
        pass
    return None


def _links(resp: requests.Response) -> list[str]:
    soup = BeautifulSoup(resp.text, "html.parser")
    return [a.get("href", "") for a in soup.find_all("a") if a.get("href")]


# --- 3GPP ---------------------------------------------------------------

def _resolve_3gpp(ref: Reference) -> ResolvedSource:
    parts = ref.code.split()
    if len(parts) != 2:
        return ResolvedSource(reference=ref, status=DocStatus.UNRESOLVED)

    series = parts[1].split(".")[0]
    folder_url = f"https://www.3gpp.org/ftp/Specs/archive/{series}_series/{parts[1]}/"
    resp = _get(folder_url)

    if not resp:
        return ResolvedSource(reference=ref, status=DocStatus.UNRESOLVED)

    # 3GPP folders list versioned .zip files, e.g. 23041-k00.zip
    zip_links = [
        l
        for l in _links(resp)
        if l.lower().endswith(".zip")
    ]

    if not zip_links:
        return ResolvedSource(
            reference=ref,
            status=DocStatus.PENDING,
            source_url=folder_url,
        )

    latest = sorted(zip_links)[-1]
    file_url = urljoin(folder_url, latest)

    return ResolvedSource(
        reference=ref,
        status=DocStatus.PENDING,
        source_url=file_url,
        version=latest,
    )


# --- IETF -----------------------------------------------------------------

def _resolve_ietf(ref: Reference) -> ResolvedSource:
    url = f"https://www.rfc-editor.org/rfc/rfc{ref.code.strip()}.html"

    return ResolvedSource(
        reference=ref,
        status=DocStatus.PENDING,
        source_url=url,
    )


# --- ETSI ------------------------------------------------------------------

def _resolve_etsi(ref: Reference) -> ResolvedSource:
    code_clean = re.sub(
        r"[A-Z]+",
        "",
        ref.code,
    ).strip()

    # "TS 102 900" -> "102900"
    digits = code_clean.replace(" ", "")

    if len(digits) < 6:
        return ResolvedSource(
            reference=ref,
            status=DocStatus.UNRESOLVED,
        )

    range_start = digits[:-2] + "00"
    range_end = digits[:-2] + "99"

    # ETSI TS ve TR belgeleri farklı dizinlerde tutuluyor.
    doc_type = (
        ref.code
        .strip()
        .split()[0]
        .lower()
    )

    if doc_type not in {"ts", "tr"}:
        doc_type = "ts"

    range_folder = (
        f"https://www.etsi.org/deliver/etsi_{doc_type}/"
        f"{range_start}_{range_end}/"
    )

    resp = _get(range_folder)

    if not resp:
        return ResolvedSource(
            reference=ref,
            status=DocStatus.UNRESOLVED,
        )

    # Sadece tam doküman kodu klasörünü seç.
    # Örneğin 102400 istenirken 102401 / 102410 vb.
    # yanlış belgelerin seçilmesini engeller.
    code_folder_url = next(
        (
            urljoin(range_folder, l)
            for l in _links(resp)
            if (
                l.rstrip("/")
                .split("/")[-1]
                == digits
            )
        ),
        None,
    )

    if not code_folder_url:
        return ResolvedSource(
            reference=ref,
            status=DocStatus.UNRESOLVED,
        )

    if not code_folder_url.endswith("/"):
        code_folder_url += "/"

    resp2 = _get(code_folder_url)

    if not resp2:
        return ResolvedSource(
            reference=ref,
            status=DocStatus.PENDING,
            source_url=code_folder_url,
        )

    # ETSI directory listing linkleri tam path olarak dönebildiği için
    # sadece linkin son path parçasını sürüm klasörü olarak kontrol et.
    version_urls = [
        urljoin(code_folder_url, l)
        for l in _links(resp2)
        if re.match(
            r"^\d",
            l.rstrip("/").split("/")[-1],
        )
    ]

    if not version_urls:
        return ResolvedSource(
            reference=ref,
            status=DocStatus.PENDING,
            source_url=code_folder_url,
        )

    version_url = sorted(version_urls)[-1]

    if not version_url.endswith("/"):
        version_url += "/"

    resp3 = _get(version_url)

    if not resp3:
        return ResolvedSource(
            reference=ref,
            status=DocStatus.PENDING,
            source_url=version_url,
        )

    pdf_url = next(
        (
            urljoin(version_url, l)
            for l in _links(resp3)
            if l.lower().endswith(".pdf")
        ),
        None,
    )

    if pdf_url:
        return ResolvedSource(
            reference=ref,
            status=DocStatus.PENDING,
            source_url=pdf_url,
        )

    return ResolvedSource(
        reference=ref,
        status=DocStatus.PENDING,
        source_url=version_url,
    )


# --- ITU-T -------------------------------------------------------------

def _resolve_itu(ref: Reference) -> ResolvedSource:
    code_clean = ref.code.strip()
    landing_url = f"https://www.itu.int/rec/T-REC-{code_clean}/en"

    resp = _get(landing_url)

    if not resp:
        return ResolvedSource(
            reference=ref,
            status=DocStatus.UNRESOLVED,
        )

    pdf_link = next(
        (
            l
            for l in _links(resp)
            if l.lower().endswith(".pdf")
        ),
        None,
    )

    if pdf_link:
        return ResolvedSource(
            reference=ref,
            status=DocStatus.PENDING,
            source_url=urljoin(landing_url, pdf_link),
        )

    # no free PDF link found on the landing page -> likely paywalled/restricted
    return ResolvedSource(
        reference=ref,
        status=DocStatus.BLOCKED,
        source_url=landing_url,
    )


def _search_google_pdf(query: str) -> str | None:
    if not API_KEY or not CX:
        return None

    url = (
        f"https://www.googleapis.com/customsearch/v1"
        f"?q={query}&key={API_KEY}&cx={CX}"
    )

    resp = _get(url)

    if resp:
        try:
            data = resp.json()

            for item in data.get("items", []):
                link = item.get("link", "")

                if link.lower().endswith(".pdf"):
                    return link

        except Exception:
            pass

    return None


def _resolve_gsma(ref: Reference) -> ResolvedSource:
    pdf_link = _search_google_pdf(
        f"site:gsma.com {ref.code.strip()} filetype:pdf"
    )

    return ResolvedSource(
        reference=ref,
        status=(
            DocStatus.PENDING
            if pdf_link
            else DocStatus.BLOCKED
        ),
        source_url=pdf_link,
    )


def _resolve_atis(ref: Reference) -> ResolvedSource:
    code_clean = (
        ref.code
        .replace("ATIS-", "")
        .replace("-", "")
        .strip()
    )

    pdf_link = _search_google_pdf(
        f"site:atis.org {code_clean} filetype:pdf"
    )

    return ResolvedSource(
        reference=ref,
        status=(
            DocStatus.PENDING
            if pdf_link
            else DocStatus.BLOCKED
        ),
        source_url=pdf_link,
    )


def _resolve_ieee(ref: Reference) -> ResolvedSource:
    pdf_link = _search_google_pdf(
        f"site:ieee.org {ref.code.strip()} filetype:pdf"
    )

    return ResolvedSource(
        reference=ref,
        status=(
            DocStatus.PENDING
            if pdf_link
            else DocStatus.BLOCKED
        ),
        source_url=pdf_link,
    )


def _resolve_oran(ref: Reference) -> ResolvedSource:
    pdf_link = _search_google_pdf(
        f"site:o-ran.org {ref.code.strip()} filetype:pdf"
    )

    return ResolvedSource(
        reference=ref,
        status=(
            DocStatus.PENDING
            if pdf_link
            else DocStatus.BLOCKED
        ),
        source_url=pdf_link,
    )


def _resolve_bbf(ref: Reference) -> ResolvedSource:
    pdf_link = _search_google_pdf(
        f"site:broadband-forum.org {ref.code.strip()} filetype:pdf"
    )

    return ResolvedSource(
        reference=ref,
        status=(
            DocStatus.PENDING
            if pdf_link
            else DocStatus.BLOCKED
        ),
        source_url=pdf_link,
    )


def _resolve_mef(ref: Reference) -> ResolvedSource:
    pdf_link = _search_google_pdf(
        f"site:mef.net {ref.code.strip()} filetype:pdf"
    )

    return ResolvedSource(
        reference=ref,
        status=(
            DocStatus.PENDING
            if pdf_link
            else DocStatus.BLOCKED
        ),
        source_url=pdf_link,
    )


RESOLVERS = {
    "3GPP": _resolve_3gpp,
    "IETF": _resolve_ietf,
    "ETSI": _resolve_etsi,
    "ITU-T": _resolve_itu,
    "GSMA": _resolve_gsma,
    "ATIS": _resolve_atis,
    "IEEE": _resolve_ieee,
    "O-RAN": _resolve_oran,
    "BBF": _resolve_bbf,
    "MEF": _resolve_mef,
}


def resolve(ref: Reference) -> ResolvedSource:
    handler = RESOLVERS.get(ref.org)

    if not handler:
        return ResolvedSource(
            reference=ref,
            status=DocStatus.UNRESOLVED,
        )

    return handler(ref)


if __name__ == "__main__":
    tests = [
        Reference(
            org="3GPP",
            code="TS 23.041",
            title="",
            raw_text="",
        ),
        Reference(
            org="IETF",
            code="4960",
            title="",
            raw_text="",
        ),
        Reference(
            org="ETSI",
            code="TS 102 900",
            title="",
            raw_text="",
        ),
        Reference(
            org="ITU-T",
            code="G.711",
            title="",
            raw_text="",
        ),
        Reference(
            org="GSMA",
            code="AD.26",
            title="",
            raw_text="",
        ),
        Reference(
            org="ATIS",
            code="0700041",
            title="",
            raw_text="",
        ),
    ]

    for ref in tests:
        result = resolve(ref)

        print(
            f"{ref.org:6s} "
            f"{ref.code:15s} "
            f"-> [{result.status.value}] "
            f"{result.source_url}"
        )
