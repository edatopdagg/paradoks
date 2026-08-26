import re
from typing import Any


SYSTEM_PROMPT = """
Sen, verilen telekomünikasyon standardı parçalarına dayanarak
cevap veren kaynak kontrollü teknik bir asistansın.

Temel kurallar:

- Yalnızca verilen standart parçalarını kullan.
- Kaynakta açıkça bulunmayan bilgi ekleme veya tahmin etme.
- Sorunun istediği teknik varlık türünü koru:
  sistem, mimari, prosedür, mesaj, protokol, arayüz,
  standart, network function, amaç, koşul veya değer.
- Farklı teknik varlıkları birbirinin yerine koyma.
  Örneğin standart numarası sistem değildir,
  mesaj adı prosedür değildir.
- Kaynaktaki teknik ilişkileri koru.
  "X uses Y", "X is defined in Y", "X supports Y"
  ifadelerinin anlamını birbirine dönüştürme.
- Teknik terimleri ve kısaltmaları kaynakta geçtiği
  anlamda kullan; açılım uydurma.
- Birden fazla kaynak varsa soruyu en doğrudan
  cevaplayan içeriğe öncelik ver.
- Soru genel bir mimari öğeyi soruyorsa, belirli bir
  hizmete özgü kullanım örneklerini genel tanım gibi sunma.
- Bir kaynak genel tanım, başka bir kaynak özel kullanım
  örneği veriyorsa cevabı genel tanıma göre oluştur.
- Kullanıcının sormadığı yan bilgileri ekleme.
- Soru birden fazla bölüm içeriyorsa her bölümü yanıtla;
  kanıtı olmayan bölümü tahmin etme.
- Kaynak listesini cevaba yazma.
- İlk cümlede doğrudan cevabı ver.
- Doğal ve teknik Türkçe kullan.
- Asla kendi uydurduğun kısaltmaları (örneğin AMM vb.) kullanma. Yalnızca soruda ve kaynaklarda açıkça geçen standart kısaltmaları (AMF, SMF, UPF vb.) veya doğrudan Türkçe/İngilizce tam adlarını kullan.
- Normalde 1-3 kısa cümle yeterlidir.
- Yalnızca sana verilen kaynak metinlerde açıkça listelenen görev ve tanımları kullan. Kaynakta geçmeyen harici terimleri veya protokol detaylarını yanıta ekleme.
- Bilgi yetersizse yalnızca:
  "Bu soruyu yanıtlamak için yeterli standart bilgisi bulunamadı."
""".strip()


# =========================================================
# ANSWER TYPE INFERENCE
# =========================================================

def infer_answer_type(
    question: str,
) -> str:
    """
    Kullanıcının hangi tür teknik varlığı
    sorduğunu deterministik olarak belirler.

    Önemli:
    Daha spesifik türler daha genel türlerden
    ÖNCE kontrol edilir.

    Örneğin:
        "hangi network function"
    ifadesi "hangi network" nedeniyle SİSTEM
    olarak sınıflandırılmamalıdır.
    """

    clean_question = (
        question
        or ""
    ).casefold()

    rules = [

        # -------------------------------------------------
        # STANDART / DOKÜMAN
        # -------------------------------------------------

        (
            (
                r"\bhangi\s+standart\w*",
                r"\bhangi\s+doküman\w*",
                r"\bhangi\s+rfc\w*",
                r"\bhangi\s+(?:3gpp\s+)?(?:standart|standard)\w*",
                r"\b(?:standart|standard)\w*\s+tanımlan\w*",
                r"\bhangi\s+rfc\b",
                r"\brfc['’]?(?:de|da)\s+tanımlan\w*",
                r"\bhangi\s+(?:doküman|document)\w*",
                r"\brfc(?:'|’)?(?:de|da)\b",
                r"\bhangi\s+specification\b",
                r"\bwhich\s+rfc\b",
                r"\bwhich\s+standard\b",
            ),
            "STANDART / DOKÜMAN",
        ),

        # -------------------------------------------------
        # ARAYÜZ / REFERANS NOKTASI
        # -------------------------------------------------

        (
            (
                r"\bhangi(?:\s+\w+){0,3}\s+arayüz\w*",
                r"\bhangi(?:\s+\w+){0,3}\s+interface\w*",
                r"\bhangi(?:\s+\w+){0,3}\s+referans\s+nokt\w*",
                r"\b\w+\s+ile\s+\w+\s+arasındaki\s+"
                r"referans\s+nokt\w*\s+hangisidir\b",
                r"\bwhich(?:\s+\w+){0,3}\s+reference\s+point\b",
            ),
            "ARAYÜZ / REFERANS NOKTASI",
        ),

        # -------------------------------------------------
        # PROTOKOL
        # -------------------------------------------------

        (
            (
                r"\bhangi(?:\s+\w+){0,3}\s+protokol\w*",
                r"\bwhich(?:\s+\w+){0,3}\s+protocol\b",
                r"\btransport\s+protocol\b",
                r"\btaşıma\s+protokol\w*",
                r"\bhangi\s+protocol\b",
            ),
            "PROTOKOL",
        ),

        # -------------------------------------------------
        # NETWORK FUNCTION
        # -------------------------------------------------

        (
            (
                r"\bhangi(?:\s+\w+){0,3}\s+network\s+function\b",
                r"\bhangi\s+nf\b",
                r"\bwhich(?:\s+\w+){0,3}\s+network\s+function\b",
                r"\bnetwork\s+function\s+(?:yürüt|gerçekleştir|yapar)",
                r"\bnetwork\s+function\b",
            ),
            "NETWORK FUNCTION",
        ),

        # -------------------------------------------------
        # PROSEDÜR
        # -------------------------------------------------

        (
            (
                r"\bhangi(?:\s+\w+){0,3}\s+prosedür\w*",
                r"\bwhich(?:\s+\w+){0,3}\s+procedure\b",
            ),
            "PROSEDÜR",
        ),

        # -------------------------------------------------
        # MESAJ
        # -------------------------------------------------

        (
            (
                r"\bhangi(?:\s+\w+){0,3}\s+mesaj\w*",
                r"\bne\s+gönder\w*",
                r"\bhangi(?:\s+\w+){0,3}\s+request\b",
                r"\bhangi(?:\s+\w+){0,3}\s+message\b",
            ),
            "MESAJ",
        ),

        # -------------------------------------------------
        # SİSTEM
        # -------------------------------------------------

        (
            (
                r"\bhangi\s+sistem\w*",
                r"\bhangi\s+şebeke\w*",
                r"\bhangi\s+network\b",
                r"\bwhich\s+system\b",
            ),
            "SİSTEM",
        ),

        # -------------------------------------------------
        # AMAÇ / İŞLEV
        # -------------------------------------------------

        (
            (
                r"\bne\s+işe\s+yar\w*",
                r"\bamacı\s+ne",
                r"\bhangi\s+amaçla\b",
                r"\bne\s+amaçla\b",
                r"\bgörevi\s+ne",
                r"\bneden\s+kullan\w*",
                r"\bwhat\s+is\s+the\s+purpose\b",
                r"\bwhat\s+does\b",
            ),
            "AMAÇ / İŞLEV",
        ),

        # -------------------------------------------------
        # KOŞUL / ZAMAN
        # -------------------------------------------------

        (
            (
                r"\bne\s+zaman\b",
                r"\bhangi\s+durum\w*",
                r"\bhangi\s+koşul\w*",
                r"\bwhen\b",
                r"\bunder\s+what\s+condition",
            ),
            "KOŞUL / ZAMAN",
        ),

        # -------------------------------------------------
        # DEĞER / LİMİT
        # -------------------------------------------------

        (
            (
                r"\bkaç\b",
                r"\bmaksimum\b",
                r"\bminimum\b",
                r"\bmaximum\b",
                r"\bminimum\b",
                r"\blimit\b",
                r"\bdeğeri\s+ne",
                r"\bkaç\s+basamak",
                r"\bkaç\s+bit",
                r"\bkaç\s+byte",
                r"\bkaç\s+saniye",
                r"\bhow\s+many\b",
                r"\bhow\s+much\b",
            ),
            "DEĞER / LİMİT",
        ),
    ]

    for patterns, answer_type in rules:
        if any(
            re.search(
                pattern,
                clean_question,
                flags=re.IGNORECASE,
            )
            for pattern in patterns
        ):
            return answer_type

    return "GENEL TEKNİK BİLGİ"


# =========================================================
# CONTEXT BUILDER
# =========================================================

def build_context(
    chunks: list[dict[str, Any]],
) -> str:
    context_parts: list[str] = []

    for index, chunk in enumerate(
        chunks,
        start=1,
    ):
        metadata = chunk.get(
            "metadata",
            {},
        )

        org = metadata.get(
            "org",
            "Bilinmiyor",
        )

        code = metadata.get(
            "code",
            "Bilinmiyor",
        )

        clause = metadata.get(
            "clause",
            "Bilinmiyor",
        )

        clause_title = metadata.get(
            "clause_title",
            "",
        )

        text = (
            chunk.get(
                "text"
            )
            or ""
        ).strip()

        header = (
            f"{org} {code} | "
            f"Madde {clause}"
        )

        if clause_title:
            header += (
                f" | {clause_title}"
            )

        context_parts.append(
            "\n".join(
                [
                    (
                        f"[KAYNAK {index}: "
                        f"{header}]"
                    ),
                    text,
                ]
            )
        )

    return "\n\n".join(
        context_parts
    )


# =========================================================
# USER PROMPT
# =========================================================

def build_user_prompt(
    question: str,
    chunks: list[dict[str, Any]],
) -> str:
    context = build_context(
        chunks
    )

    answer_type = infer_answer_type(
        question
    )

    return f"""
SORU:
{question}

BEKLENEN CEVAP TÜRÜ:
{answer_type}

KAYNAKLAR:
{context}

Yalnızca bu kaynaklara dayanarak soruyu cevapla.

Sorulan teknik varlığın türünü değiştirme.
İlk cümlede doğrudan cevabı doğal Türkçeyle ver.
Standart numarasını yalnızca kullanıcı standart soruyorsa
veya açıklama için gerçekten gerekiyorsa kullan.
Kullanıcının sormadığı ayrıntıları ekleme.
Genel bir teknik öğe soruluyorsa belirli bir hizmete özgü
örnekleri genel tanımın parçası gibi sunma.
Soruda birden fazla istek varsa her birini cevapla;
bir bölüm kaynaklarda yoksa bunu açıkça belirt.
""".strip()
