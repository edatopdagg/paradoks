import os
import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import quote_plus, urljoin
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


def _probe_http_status(
    url: str,
) -> int | None:
    """
    _get() başarısız olduğunda HTTP cevabının
    nedenini ayırt etmek için yalnız status code döndürür.

    Özellikle bazı resmi 3GPP archive klasörleri
    403 Forbidden dönebildiği için kullanılır.
    """

    try:
        response = requests.get(
            url,
            headers=HEADERS,
            timeout=TIMEOUT,
            allow_redirects=True,
        )

        return response.status_code

    except requests.RequestException:
        return None


def _links(resp: requests.Response) -> list[str]:
    soup = BeautifulSoup(resp.text, "html.parser")
    return [a.get("href", "") for a in soup.find_all("a") if a.get("href")]


# --- 3GPP ---------------------------------------------------------------

def _three_gpp_archive_filename(
    link: str,
    expected_number: str,
) -> str | None:
    clean_link = (
        link.split("?", 1)[0]
        .split("#", 1)[0]
        .rstrip("/")
    )

    filename = clean_link.rsplit(
        "/",
        1,
    )[-1]

    pattern = (
        rf"{re.escape(expected_number)}"
        r"-[0-9a-zA-Z]{3}\.zip"
    )

    if not re.fullmatch(
        pattern,
        filename,
        flags=re.IGNORECASE,
    ):
        return None

    return filename


def _resolve_3gpp(ref: Reference) -> ResolvedSource:
    parts = ref.code.split()
    if len(parts) != 2:
        return ResolvedSource(reference=ref, status=DocStatus.UNRESOLVED)

    series = parts[1].split(".")[0]
    folder_url = f"https://www.3gpp.org/ftp/Specs/archive/{series}_series/{parts[1]}/"
    resp = _get(folder_url)

    if not resp:
        status_code = _probe_http_status(
            folder_url
        )

        if status_code == 403:
            return ResolvedSource(
                reference=ref,
                status=DocStatus.BLOCKED,
                source_url=folder_url,
            )

        return ResolvedSource(
            reference=ref,
            status=DocStatus.UNRESOLVED,
            source_url=folder_url,
        )

    # Noktayi kaldirirken multipart ekini korur.
    # 23.041   -> 23041
    # 38.101-1 -> 38101-1
    expected_number = (
        parts[1].replace(".", "")
    )

    # Yaln?zca yay?mlanm?? standart s?r?m paketlerini kabul et.
    # ?rnek: 23041-k00.zip
    zip_links = [
        link
        for link in _links(resp)
        if _three_gpp_archive_filename(
            link,
            expected_number,
        )
        is not None
    ]

    if not zip_links:
        return ResolvedSource(
            reference=ref,
            status=DocStatus.PENDING,
            source_url=folder_url,
        )

    latest = max(
        zip_links,
        key=lambda link: (
            _three_gpp_archive_filename(
                link,
                expected_number,
            )
            or ""
        ).casefold(),
    )

    file_url = urljoin(
        folder_url,
        latest,
    )

    return ResolvedSource(
        reference=ref,
        status=DocStatus.PENDING,
        source_url=file_url,
        version=(
            _three_gpp_archive_filename(
                latest,
                expected_number,
            )
            or ""
        ),
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

def _resolve_itu(
    ref: Reference,
) -> ResolvedSource:
    """
    ITU-T Recommendation resolver.

    Generic Recommendation referanslarında:
    - BASE Recommendation primary kaynaktır.
    - Amendment / Corrigendum / Appendix / Erratum,
      yalnız açıkça isteniyorsa primary seçilir.
    - Bir component daha yeni tarihli diye generic
      Recommendation'ın yerine geçmez.
    """

    code_clean = ref.code.strip()

    landing_url = (
        "https://www.itu.int/rec/"
        f"T-REC-{code_clean}/en"
    )

    response = _get(
        landing_url
    )

    if not response:
        return ResolvedSource(
            reference=ref,
            status=DocStatus.UNRESOLVED,
            source_url=landing_url,
        )

    links = _links(
        response
    )

    version_pattern = re.compile(
        (
            r"parent=T-REC-"
            rf"{re.escape(code_clean)}"
            r"-(?P<date>\d{6})-"
            r"(?P<status>[A-Z])"
            r"(?P<suffix>![^&\"']+)?"
        ),
        flags=re.IGNORECASE,
    )

    candidates = []

    for link in links:

        match = version_pattern.search(
            link
        )

        if match is None:
            continue

        if "lang=en" not in link.casefold():
            continue

        suffix = (
            match.group("suffix")
            or ""
        )

        suffix_lower = (
            suffix.casefold()
        )

        if not suffix:
            kind = "base"

        elif suffix_lower.startswith(
            "!amd"
        ):
            kind = "amendment"

        elif suffix_lower.startswith(
            "!cor"
        ):
            kind = "corrigendum"

        elif suffix_lower.startswith(
            "!app"
        ):
            kind = "appendix"

        elif suffix_lower.startswith(
            "!err"
        ):
            kind = "erratum"

        else:
            kind = "other"

        candidates.append(
            {
                "date": match.group("date"),
                "status": match.group("status"),
                "suffix": suffix,
                "kind": kind,
                "link": link,
            }
        )

    reference_text = " ".join(
        (
            ref.title or "",
            ref.raw_text or "",
        )
    )

    normalized_reference = re.sub(
        r"\s+",
        " ",
        reference_text,
    ).strip().casefold()

    explicit_kind = None
    explicit_number = None

    component_patterns = (
        (
            "amendment",
            r"\b(?:amendment|amd\.?)\s*(\d+)",
        ),
        (
            "corrigendum",
            r"\b(?:corrigendum|cor\.?)\s*(\d+)",
        ),
        (
            "appendix",
            r"\b(?:appendix|app\.?)\s*([ivxlcdm]+|\d+)",
        ),
        (
            "erratum",
            r"\b(?:erratum|err\.?)\s*(\d+)",
        ),
    )

    for kind, pattern in component_patterns:

        match = re.search(
            pattern,
            reference_text,
            flags=re.IGNORECASE,
        )

        if match is None:
            continue

        explicit_kind = kind
        explicit_number = (
            match.group(1)
        )

        break

    # --------------------------------------------------------
    # I.112 semantic identity
    # --------------------------------------------------------
    #
    # 3GPP referansı "Appendix I" yazmıyor fakat
    # "General telecommunication terminology and definitions"
    # doğrudan I.112 Appendix I içeriğinin kimliğidir.
    # --------------------------------------------------------

    if (
        code_clean.upper() == "I.112"
        and (
            "general telecommunication "
            "terminology and definitions"
        )
        in normalized_reference
    ):
        explicit_kind = "appendix"
        explicit_number = "1"

    # --------------------------------------------------------
    # GENERIC → yalnız BASE
    # EXPLICIT COMPONENT → yalnız o component
    # --------------------------------------------------------

    if explicit_kind is None:

        candidate_pool = [
            candidate
            for candidate in candidates
            if candidate["kind"] == "base"
        ]

    else:

        candidate_pool = [
            candidate
            for candidate in candidates
            if candidate["kind"] == explicit_kind
        ]

        if explicit_number:

            if explicit_kind == "appendix":
                expected = (
                    f"!app{explicit_number}"
                    .casefold()
                )

            elif explicit_kind == "amendment":
                expected = (
                    f"!amd{explicit_number}"
                    .casefold()
                )

            elif explicit_kind == "corrigendum":
                expected = (
                    f"!cor{explicit_number}"
                    .casefold()
                )

            elif explicit_kind == "erratum":
                expected = (
                    f"!err{explicit_number}"
                    .casefold()
                )

            else:
                expected = ""

            if expected:

                numbered_pool = [
                    candidate
                    for candidate
                    in candidate_pool
                    if (
                        candidate["suffix"]
                        .casefold()
                        .startswith(expected)
                    )
                ]

                if numbered_pool:
                    candidate_pool = (
                        numbered_pool
                    )

    if not candidate_pool:

        return ResolvedSource(
            reference=ref,
            status=DocStatus.BLOCKED,
            source_url=landing_url,
        )

    # Aynı candidate türündeki en güncel sürüm.
    selected = max(
        candidate_pool,
        key=lambda candidate: (
            candidate["date"],
            (
                candidate["status"]
                .casefold()
                == "i"
            ),
        ),
    )

    source_page_url = urljoin(
        landing_url,
        selected["link"],
    )

    version_response = _get(
        source_page_url
    )

    if not version_response:

        return ResolvedSource(
            reference=ref,
            status=DocStatus.UNRESOLVED,
            source_url=source_page_url,
        )

    page_links = _links(
        version_response
    )

    pdf_link = next(
        (
            link
            for link in page_links
            if (
                "dologin_pub.asp"
                in link.casefold()
                and "pdf-e"
                in link.casefold()
            )
        ),
        None,
    )

    if pdf_link is None:

        pdf_link = next(
            (
                link
                for link in page_links
                if link.casefold().endswith(
                    ".pdf"
                )
            ),
            None,
        )

    if pdf_link:

        return ResolvedSource(
            reference=ref,
            status=DocStatus.PENDING,
            source_url=urljoin(
                source_page_url,
                pdf_link,
            ),
        )

    return ResolvedSource(
        reference=ref,
        status=DocStatus.BLOCKED,
        source_url=source_page_url,
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


def _resolve_gsma(
    ref: Reference,
) -> ResolvedSource:
    code_clean = ref.code.strip()

    pdf_link = _search_google_pdf(
        "site:gsma.com "
        f"{code_clean} filetype:pdf"
    )

    landing_url = (
        "https://www.gsma.com/"
        f"?s={quote_plus(code_clean)}"
    )

    return ResolvedSource(
        reference=ref,
        status=(
            DocStatus.PENDING
            if pdf_link
            else DocStatus.BLOCKED
        ),
        source_url=(
            pdf_link
            or landing_url
        ),
    )


def _resolve_atis(
    ref: Reference,
) -> ResolvedSource:
    code_clean = (
        ref.code
        .replace("ATIS-", "")
        .replace("-", "")
        .strip()
    )

    pdf_link = _search_google_pdf(
        "site:atis.org "
        f"{code_clean} filetype:pdf"
    )

    landing_url = (
        "https://atis.org/"
        f"?s={quote_plus(code_clean)}"
    )

    return ResolvedSource(
        reference=ref,
        status=(
            DocStatus.PENDING
            if pdf_link
            else DocStatus.BLOCKED
        ),
        source_url=(
            pdf_link
            or landing_url
        ),
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
