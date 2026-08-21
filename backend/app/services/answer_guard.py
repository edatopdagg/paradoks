import re
from typing import Any

from app.services.prompt_builder import (
    build_context,
    infer_answer_type,
)


# ---------------------------------------------------------
# GENEL PATTERNLER
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


# ---------------------------------------------------------
# TEMEL YARDIMCILAR
# ---------------------------------------------------------

def _first_sentence(
    text: str,
) -> str:
    clean_text = (
        text
        or ""
    ).strip()

    if not clean_text:
        return ""

    parts = re.split(
        r"(?<=[.!?])\s+",
        clean_text,
        maxsplit=1,
    )

    return parts[0].strip()


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


# ---------------------------------------------------------
# KAYNAKTAN SİSTEM ADLARINI ÇIKAR
# ---------------------------------------------------------

def _extract_system_terms(
    chunks: list[dict[str, Any]],
) -> list[str]:
    """
    Kaynak metinlerde açıkça 'System' olarak
    geçen teknik varlıkları çıkarır.

    Örnek:
        5G system
        IMS System
        EPS System

    Amaç teknik cevabı tahmin etmek değil,
    sistem sorusunda LLM'in tamamen başka tür
    bir varlığı sistem diye sunmasını yakalamaktır.
    """

    found: list[str] = []
    seen: set[str] = set()

    for chunk in chunks:
        text = (
            chunk.get("text")
            or ""
        )

        for match in (
            SYSTEM_TERM_PATTERN.finditer(
                text
            )
        ):
            value = (
                match.group(1)
                .strip()
            )

            normalized = (
                _normalize(value)
            )

            if normalized in seen:
                continue

            seen.add(
                normalized
            )

            found.append(
                value
            )

    return found


def _system_term_aliases(
    term: str,
) -> set[str]:
    """
    Kaynakta geçen İngilizce teknik sistem
    adının Türkçe cevapta bulunabilecek basit
    varyantlarını oluşturur.

    Örnek:
        5G system
        5G System
        5G sistemi
        5GS
    """

    normalized = _normalize(
        term
    )

    aliases = {
        normalized,
    }

    if normalized.endswith(
        " system"
    ):
        base = normalized[
            :-len(" system")
        ].strip()

        if base:
            aliases.add(
                f"{base} sistemi"
            )

    if normalized == "5g system":
        aliases.add(
            "5gs"
        )

    return aliases


# ---------------------------------------------------------
# DOKÜMANIN CEVAP TÜRÜ YERİNE KULLANILMASI
# ---------------------------------------------------------

def _document_used_as_answer(
    answer_type: str,
    first_sentence: str,
) -> bool:
    """
    Kullanıcı sistem/prosedür/mesaj vb. sorarken
    LLM'in TS/RFC gibi doküman kodunu doğrudan
    teknik cevap yerine koyup koymadığını kontrol eder.
    """

    if answer_type == (
        "STANDART / DOKÜMAN"
    ):
        return False

    if not DOCUMENT_CODE_PATTERN.search(
        first_sentence
    ):
        return False

    lower_sentence = (
        first_sentence.casefold()
    )

    document_words = (
        "standart",
        "standard",
        "doküman",
        "document",
        "specification",
    )

    return any(
        word in lower_sentence
        for word in document_words
    )


# ---------------------------------------------------------
# ANA VALIDATION
# ---------------------------------------------------------

def validate_answer(
    question: str,
    reply: str,
    chunks: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    LLM cevabına hafif, deterministik bir
    doğrulama uygular.

    Önemli:
    Kaynaktan çıkarılabilen cevap türü evidence'ları
    validation başarısız olsa bile korunur.
    Böylece repair aşaması kör çalışmaz.
    """

    answer_type = (
        infer_answer_type(
            question
        )
    )

    clean_reply = (
        reply
        or ""
    ).strip()

    # -----------------------------------------------------
    # EVIDENCE'I ÖNCEDEN ÇIKAR
    # -----------------------------------------------------

    evidence_terms: list[str] = []

    if answer_type == "SİSTEM":
        evidence_terms = (
            _extract_system_terms(
                chunks
            )
        )

    # -----------------------------------------------------
    # BOŞ CEVAP
    # -----------------------------------------------------

    if not clean_reply:
        return {
            "valid": False,
            "answer_type": answer_type,
            "reason": (
                "Model boş cevap üretti."
            ),
            "evidence_terms": evidence_terms,
        }

    first_sentence = (
        _first_sentence(
            clean_reply
        )
    )

    # -----------------------------------------------------
    # DOKÜMAN KODUNUN TEKNİK VARLIK YERİNE KONMASI
    # -----------------------------------------------------

    if _document_used_as_answer(
        answer_type=answer_type,
        first_sentence=first_sentence,
    ):
        return {
            "valid": False,
            "answer_type": answer_type,
            "reason": (
                "Standart/doküman kodu, "
                "sorulan teknik varlığın "
                "yerine cevap olarak kullanılmış."
            ),
            "evidence_terms": evidence_terms,
        }

    # -----------------------------------------------------
    # SİSTEM SORUSU
    # -----------------------------------------------------

    if (
        answer_type == "SİSTEM"
        and evidence_terms
    ):
        reply_normalized = (
            _normalize(
                clean_reply
            )
        )

        matched = False

        for term in evidence_terms:
            aliases = (
                _system_term_aliases(
                    term
                )
            )

            if any(
                alias in reply_normalized
                for alias in aliases
            ):
                matched = True
                break

        if not matched:
            return {
                "valid": False,
                "answer_type": answer_type,
                "reason": (
                    "Sistem sorusuna verilen "
                    "cevap, kaynak metinde "
                    "açıkça System olarak geçen "
                    "teknik varlıklardan hiçbirini "
                    "içermiyor."
                ),
                "evidence_terms": evidence_terms,
            }

    # -----------------------------------------------------
    # PASS
    # -----------------------------------------------------

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
    """
    İlk Ollama cevabı guard'dan geçemezse
    ikinci ve yalnızca bir kez kullanılacak
    düzeltme promptunu oluşturur.
    """

    context = build_context(
        chunks
    )

    answer_type = validation.get(
        "answer_type",
        "GENEL TEKNİK BİLGİ",
    )

    reason = validation.get(
        "reason",
        "",
    )

    evidence_terms = validation.get(
        "evidence_terms",
        [],
    )

    evidence_text = (
        ", ".join(
            evidence_terms
        )
        if evidence_terms
        else "Yok"
    )

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
- Standart/doküman kodunu sistem, prosedür,
  mesaj, protokol veya arayüz yerine koyma.
- Kaynakta System olarak geçen bir varlık sistem
  sorusunun cevabıysa onu teknik anlamını bozmadan kullan.
- Kullanıcının sormadığı ayrıntıları ekleme.
- Beklenen cevap türü SİSTEM ise ve yukarıda
  "KAYNAKTA TESPİT EDİLEN İLGİLİ TEKNİK TERİMLER"
  listesinde System olarak tanımlanan bir varlık varsa,
  sistem cevabını bu kaynak terimine göre oluştur.
- Doğal Türkçe cümle kullan.
""".strip()


# ---------------------------------------------------------
# GÜVENLİ FALLBACK
# ---------------------------------------------------------

def build_guard_fallback(
    validation: dict[str, Any],
) -> str:
    """
    Repair cevabı da doğrulamadan geçemezse
    yanlış teknik bilgi göstermek yerine güvenli
    bir cevap döndürür.

    SİSTEM türünde kaynakta açıkça bulunan sistem
    terimi varsa yalnızca onu kullanabilir.
    """

    answer_type = validation.get(
        "answer_type",
        "",
    )

    evidence_terms = validation.get(
        "evidence_terms",
        [],
    )

    if (
        answer_type == "SİSTEM"
        and evidence_terms
    ):
        primary_system = (
            evidence_terms[0]
        )

        return (
            "Kaynak metne göre ilgili sistem "
            f"{primary_system} olarak belirtilir."
        )

    return (
        "Kaynaklar bulundu ancak doğrudan ve "
        "güvenilir bir cevap oluşturulamadı."
    )