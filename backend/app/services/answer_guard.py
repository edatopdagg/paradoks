import re
from typing import Any

from app.services.prompt_builder import (
    build_context,
    infer_answer_type,
)

# ---------------------------------------------------------
# GENEL PATTERNLER & İZİN VERİLEN TERİMLER
# ---------------------------------------------------------

DOCUMENT_CODE_PATTERN = re.compile(
    r"\b(?:"
    r"TS|TR|RFC|EN|ES|Recommendation"
    r")\s*[A-Z]?\s*\d[\d.\-]*\b",
    flags=re.IGNORECASE,
)

SYSTEM_TERM_PATTERN = re.compile(
    r"\b("
    r"(?:\dG|[A-Z][A-Z0-9\-]{1,})"
    r"(?:\s+[A-Za-z0-9\-]+){0,3}"
    r"\s+[Ss]ystem"
    r")\b"
)

# Modelin genel telekom açıklamalarında ve referanslama yaparken kullandığı standart/meşru terimler
ALLOWED_TELECOM_IDENTIFIERS = {
    # Şablon ve Alıntı İfadeleri (Halüsinasyon sayılmaması gerekenler)
    "kaynak",
    "kaynaklar",
    "standart",
    "standartlar",
    "doküman",
    "dokuman",
    "madde",
    "bölüm",
    "bolum",
    "tablo",
    "şekil",
    "sekil",
    "ek",
    "clause",
    "section",
    "annex",
    "table",
    "figure",
    "session",
    "request",
    "response",
    "accept",
    "reject",
    "procedure",
    "message",
    # 5G/Telekom Terimleri ve Arayüzleri
    "sdf",
    "gating",
    "qos",
    "pdu",
    "dnn",
    "ue",
    "ran",
    "ng-ran",
    "gnb",
    "amf",
    "smf",
    "upf",
    "ausf",
    "udm",
    "pcf",
    "nssf",
    "nrf",
    "nas",
    "n1",
    "n2",
    "n3",
    "n4",
    "n6",
    "n9",
    "n11",
    "n12",
    "n14",
    "n15",
    "n26",
    "n50",
    "f1",
    "e1",
    "x2",
    "xn",
    "amm",
    "http",
    "tcp",
    "udp",
    "sctp",
    "quic",
    "ip",
    "ipv4",
    "ipv6",
    "tai",
    "pra",
    "mbs",
}

# ---------------------------------------------------------
# TEMEL YARDIMCILAR
# ---------------------------------------------------------

def _first_sentence(text: str) -> str:
    clean_text = (text or "").strip()
    if not clean_text:
        return ""
    parts = re.split(r"(?<=[.!?])\s+", clean_text, maxsplit=1)
    return parts[0].strip()


def _normalize(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").strip().casefold())


def _build_evidence_text(chunks: list[dict[str, Any]]) -> str:
    parts: list[str] = []
    for chunk in chunks:
        metadata = chunk.get("metadata", {})
        parts.extend(
            (
                str(chunk.get("text", "")),
                str(metadata.get("org", "")),
                str(metadata.get("code", "")),
                str(metadata.get("clause", "")),
                str(metadata.get("clause_title", "")),
            )
        )
    return _normalize(" ".join(parts))


def _technical_identifiers(value: str) -> list[str]:
    """HTTP, QoS, IoT, N3 gibi güçlü teknik işaretleri çıkarır."""
    identifiers: list[str] = []
    seen: set[str] = set()

    pattern = re.compile(
        r"\b(?:"
        r"[A-Z]{2,}[A-Z0-9/.-]*"
        r"|[A-Z][a-z0-9]*[A-Z][A-Za-z0-9/.-]*"
        r"|N\d{1,3}"
        r")\b"
    )

    for match in pattern.finditer(value or ""):
        raw_identifier = match.group(0)
        identifier = raw_identifier.strip("-/.,:;()[]")
        if not identifier:
            continue

        normalized = identifier.casefold()
        if normalized in seen:
            continue

        seen.add(normalized)
        identifiers.append(identifier)

    return identifiers


def _unsupported_technical_claims(
    question: str,
    reply: str,
    chunks: list[dict[str, Any]],
) -> list[str]:
    """Kaynağa dayanmayan güçlü teknik identifier/değerleri bulur."""
    evidence = _build_evidence_text(chunks)
    normalized_question = _normalize(question)

    unsupported: list[str] = []

    for identifier in _technical_identifiers(reply):
        normalized = identifier.casefold()

        # Whitelist, kaynak metin veya soruda varsa geçerli say
        if (
            normalized in ALLOWED_TELECOM_IDENTIFIERS
            or normalized in evidence
            or normalized in normalized_question
        ):
            continue

        unsupported.append(identifier)

    # Durum kodları kontrolü (HTTP vb.)
    for status_code in re.findall(r"(?<!\d)([1-5]\d{2})(?!\d)", reply or ""):
        if (
            status_code in evidence
            or status_code in normalized_question
        ):
            continue
        unsupported.append(status_code)

    # Parantez içi kısaltma açılımları kontrolü
    for match in re.finditer(r"\b([A-Z][A-Za-z0-9/.-]{1,})\s*\(([^)]+)\)", reply or ""):
        abbreviation = match.group(1).strip("-/.,:;()[]")
        expansion = _normalize(match.group(2))

        if (
            not expansion
            or abbreviation.casefold() in ALLOWED_TELECOM_IDENTIFIERS
            or expansion in evidence
        ):
            continue

        unsupported.append(f"{abbreviation} ({match.group(2).strip()})")

    return list(dict.fromkeys(unsupported))


# ---------------------------------------------------------
# KAYNAKTAN SİSTEM ADLARINI ÇIKAR
# ---------------------------------------------------------

def _extract_system_terms(chunks: list[dict[str, Any]]) -> list[str]:
    found: list[str] = []
    seen: set[str] = set()

    for chunk in chunks:
        text = chunk.get("text") or ""
        for match in SYSTEM_TERM_PATTERN.finditer(text):
            value = match.group(1).strip()
            normalized = _normalize(value)

            if normalized in seen:
                continue

            seen.add(normalized)
            found.append(value)

    return found


def _system_term_aliases(term: str) -> set[str]:
    normalized = _normalize(term)
    aliases = {normalized}

    if normalized.endswith(" system"):
        base = normalized[:-len(" system")].strip()
        if base:
            aliases.add(f"{base} sistemi")

    if normalized == "5g system":
        aliases.add("5gs")

    return aliases


# ---------------------------------------------------------
# DOKÜMANIN CEVAP TÜRÜ YERİNE KULLANILMASI
# ---------------------------------------------------------

def _document_used_as_answer(answer_type: str, first_sentence: str) -> bool:
    if answer_type == "STANDART / DOKÜMAN":
        return False

    if not DOCUMENT_CODE_PATTERN.search(first_sentence):
        return False

    lower_sentence = first_sentence.casefold()

    # Eğer cümlede beklenen türün kendisi (mesaj, prosedür, arayüz adı vb.) zaten geçiyorsa doküman sadece atıftır
    if any(k in lower_sentence for k in ("request", "response", "accept", "reject", "procedure", "referans", "reference point", "protocol")):
        return False

    document_words = (
        "standart",
        "standard",
        "doküman",
        "document",
        "specification",
    )

    return any(word in lower_sentence for word in document_words)


# ---------------------------------------------------------
# ANA VALIDATION
# ---------------------------------------------------------

def validate_answer(
    question: str,
    reply: str,
    chunks: list[dict[str, Any]],
) -> dict[str, Any]:
    answer_type = infer_answer_type(question)
    clean_reply = (reply or "").strip()

    evidence_terms: list[str] = []
    if answer_type == "SİSTEM":
        evidence_terms = _extract_system_terms(chunks)

    if not clean_reply:
        return {
            "valid": False,
            "answer_type": answer_type,
            "reason": "Model boş cevap üretti.",
            "evidence_terms": evidence_terms,
        }

    first_sentence = _first_sentence(clean_reply)

    if _document_used_as_answer(answer_type=answer_type, first_sentence=first_sentence):
        return {
            "valid": False,
            "answer_type": answer_type,
            "reason": (
                "Standart/doküman kodu, sorulan teknik varlığın "
                "yerine cevap olarak kullanılmış."
            ),
            "evidence_terms": evidence_terms,
        }

    unsupported_claims = _unsupported_technical_claims(
        question=question,
        reply=clean_reply,
        chunks=chunks,
    )

    if unsupported_claims:
        return {
            "valid": False,
            "answer_type": answer_type,
            "reason": (
                "Cevapta kaynaklarda veya soruda bulunmayan "
                "teknik identifier/değer kullanılmış: "
                + ", ".join(unsupported_claims)
            ),
            "evidence_terms": evidence_terms,
            "unsupported_claims": unsupported_claims,
        }

    if answer_type == "SİSTEM" and evidence_terms:
        reply_normalized = _normalize(clean_reply)
        matched = False

        for term in evidence_terms:
            aliases = _system_term_aliases(term)
            if any(alias in reply_normalized for alias in aliases):
                matched = True
                break

        if not matched:
            return {
                "valid": False,
                "answer_type": answer_type,
                "reason": (
                    "Sistem sorusuna verilen cevap, kaynak metinde "
                    "açıkça System olarak geçen teknik varlıklardan hiçbirini içermiyor."
                ),
                "evidence_terms": evidence_terms,
            }

    return {
        "valid": True,
        "answer_type": answer_type,
        "reason": "",
        "evidence_terms": evidence_terms,
    }


# ---------------------------------------------------------
# REPAIR PROMPT
# ---------------------------------------------------------

def build_repair_prompt(
    question: str,
    bad_reply: str,
    chunks: list[dict[str, Any]],
    validation: dict[str, Any],
) -> str:
    context = build_context(chunks)
    answer_type = validation.get("answer_type", "GENEL TEKNİK BİLGİ")
    reason = validation.get("reason", "")
    evidence_terms = validation.get("evidence_terms", [])
    evidence_text = ", ".join(evidence_terms) if evidence_terms else "Yok"

    return f"""
KULLANICI SORUSU:
{question}

BEKLENEN CEVAP TÜRÜ:
{answer_type}

ÖNCEKİ CEVAP:
{bad_reply}

ÖNCEKİ CEVAPTA TESPİT EDİLEN HATA:
{reason}

KAYNAKTA TESPİT EDİLEN İLGİLİ TEKNİK TERİMLER:
{evidence_text}

KAYNAKLAR:
{context}

Önceki cevabı düzelt.

Kurallar:
- Yalnızca kaynakları kullan.
- Beklenen cevap türünü değiştirme.
- İlk cümlede doğrudan cevabı ver.
- Standart/doküman kodunu sistem, prosedür, mesaj, protokol veya arayüz yerine koyma.
- Kaynakta System olarak geçen bir varlık sistem sorusunun cevabıysa onu teknik anlamını bozmadan kullan.
- Kullanıcının sormadığı ayrıntıları ekleme.
- Beklenen cevap türü SİSTEM ise ve yukarıda "KAYNAKTA TESPİT EDİLEN İLGİLİ TEKNİK TERİMLER" listesinde System olarak tanımlanan bir varlık varsa, sistem cevabını bu kaynak terimine göre oluştur.
- Doğal Türkçe cümle kullan.
""".strip()


# ---------------------------------------------------------
# GÜVENLİ FALLBACK
# ---------------------------------------------------------

def build_guard_fallback(validation: dict[str, Any]) -> str:
    answer_type = validation.get("answer_type", "")
    evidence_terms = validation.get("evidence_terms", [])

    if answer_type == "SİSTEM" and evidence_terms:
        primary_system = evidence_terms[0]
        return f"Kaynak metne göre ilgili sistem {primary_system} olarak belirtilir."

    return "Kaynaklar bulundu ancak doğrudan ve güvenilir bir cevap oluşturulamadı."