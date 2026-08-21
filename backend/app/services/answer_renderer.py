import re
from typing import Any


# =========================================================
# GENEL AYARLAR
# =========================================================

SUPPORTED_ANSWER_TYPES = {
    "SİSTEM",
    "PROSEDÜR",
    "MESAJ",
    "STANDART / DOKÜMAN",
    "ARAYÜZ / REFERANS NOKTASI",
    "PROTOKOL",
    "NETWORK FUNCTION",
    "DEĞER / LİMİT",
}


# =========================================================
# NORMALIZATION
# =========================================================

def _clean_text(
    value: str,
) -> str:
    return re.sub(
        r"\s+",
        " ",
        (
            value
            or ""
        ).strip(),
    )


def _normalize(
    value: str,
) -> str:
    return _clean_text(
        value
    ).casefold()


# =========================================================
# DISPLAY FORMAT
# =========================================================

def _format_primary_answer(
    primary_answer: str,
    answer_type: str,
) -> str:
    """
    Kaynaktan çıkarılan teknik entity'nin
    anlamını değiştirmeden yalnızca gösterim
    biçimini düzenler.

    Örnek:
        5G system -> 5G System

    Teknik terim uydurmaz veya açılım eklemez.
    """

    value = _clean_text(
        primary_answer
    )

    if answer_type == "SİSTEM":
        value = re.sub(
            r"\bsystem\b",
            "System",
            value,
            flags=re.IGNORECASE,
        )

        value = re.sub(
            r"\bsubsystem\b",
            "Subsystem",
            value,
            flags=re.IGNORECASE,
        )

    return value


# =========================================================
# SORUNUN ÖZNESİNİ ÇIKAR
# =========================================================

def _extract_subject_before_question_phrase(
    question: str,
    patterns: tuple[str, ...],
) -> str:
    """
    'X hangi sistemde kullanılır?'
    gibi sorularda X kısmını çıkarır.

    Bu metni yeniden üretmez;
    kullanıcının kendi ifadesini korur.
    """

    clean_question = (
        _clean_text(
            question
        )
        .rstrip("?.!")
    )

    for pattern in patterns:
        match = re.search(
            pattern,
            clean_question,
            flags=re.IGNORECASE,
        )

        if not match:
            continue

        subject = (
            clean_question[
                :match.start()
            ]
            .strip(" ,:-")
        )

        if subject:
            return subject

    return ""


# =========================================================
# SİSTEM
# =========================================================

def _render_system_answer(
    question: str,
    primary_answer: str,
) -> str:
    system_name = (
        _format_primary_answer(
            primary_answer,
            "SİSTEM",
        )
    )

    # ---------------------------------------------
    # "X hangi sistemde / hangi sistemden..."
    # ---------------------------------------------

    subject = (
        _extract_subject_before_question_phrase(
            question,
            (
                r"\bhangi\s+sistem(?:de|den|da|dan)?\b",
                r"\bhangi\s+şebeke(?:de|den|da|dan)?\b",
                r"\bhangi\s+network(?:te|ten|de|den)?\b",
            ),
        )
    )

    if subject:
        lower_question = (
            question.casefold()
        )

        if (
            "kullan" in lower_question
            or "çalış" in lower_question
            or "yer al" in lower_question
        ):
            return (
                f"{subject} "
                f"{system_name} içinde kullanılır."
            )

        return (
            f"{subject} için ilgili sistem "
            f"{system_name}'dır."
        )

    # ---------------------------------------------
    # Genel güvenli form
    # ---------------------------------------------

    return (
        f"İlgili sistem "
        f"{system_name}'dır."
    )


# =========================================================
# PROSEDÜR
# =========================================================

def _render_procedure_answer(
    question: str,
    primary_answer: str,
) -> str:
    procedure = _clean_text(
        primary_answer
    )

    return (
        f"İlgili prosedür "
        f"{procedure}'dür."
    )


# =========================================================
# MESAJ
# =========================================================

def _render_message_answer(
    question: str,
    primary_answer: str,
) -> str:
    message = _clean_text(
        primary_answer
    )

    return (
        f"İlgili mesaj "
        f"{message}'tır."
    )


# =========================================================
# STANDART / DOKÜMAN
# =========================================================

def _render_document_answer(
    question: str,
    primary_answer: str,
) -> str:
    document = _clean_text(
        primary_answer
    )

    return (
        f"İlgili standart veya doküman "
        f"{document}'dır."
    )


# =========================================================
# ARAYÜZ / REFERANS NOKTASI
# =========================================================

def _render_interface_answer(
    question: str,
    primary_answer: str,
) -> str:
    interface = _clean_text(
        primary_answer
    )

    return (
        f"İlgili arayüz veya referans noktası "
        f"{interface}'dır."
    )


# =========================================================
# PROTOKOL
# =========================================================

def _render_protocol_answer(
    question: str,
    primary_answer: str,
) -> str:
    protocol = _clean_text(
        primary_answer
    )

    return (
        f"İlgili protokol "
        f"{protocol}'dür."
    )


# =========================================================
# NETWORK FUNCTION
# =========================================================

def _render_network_function_answer(
    question: str,
    primary_answer: str,
) -> str:
    network_function = _clean_text(
        primary_answer
    )

    return (
        f"İlgili network function "
        f"{network_function}'dır."
    )


# =========================================================
# DEĞER / LİMİT
# =========================================================

def _render_value_answer(
    question: str,
    primary_answer: str,
) -> str:
    value = _clean_text(
        primary_answer
    )

    return (
        f"Kaynakta belirtilen değer "
        f"{value}'dır."
    )


# =========================================================
# ANA RENDERER
# =========================================================

def render_composed_answer(
    question: str,
    composition: dict[str, Any],
) -> dict[str, Any]:
    """
    Composer tarafından doğrulanmış cevap çekirdeğini
    deterministik şekilde kullanıcı cevabına dönüştürür.

    Kritik kurallar:

    - Teknik cevabı değiştirmez.
    - Yeni teknik bilgi eklemez.
    - LLM kullanmaz.
    - Sadece high-confidence primary answer varsa
      doğrudan render eder.
    """

    answer_type = str(
        composition.get(
            "answer_type",
            "",
        )
    ).strip()

    primary_answer = str(
        composition.get(
            "primary_answer",
            "",
        )
    ).strip()

    confidence = str(
        composition.get(
            "confidence",
            "low",
        )
    ).strip().casefold()

    # -----------------------------------------------------
    # HIGH CONFIDENCE DEĞİL
    # -----------------------------------------------------

    if confidence != "high":
        return {
            "success": False,
            "reply": "",
            "reason": (
                "Composer güven seviyesi high değil."
            ),
            "answer_type": answer_type,
            "primary_answer": primary_answer,
        }

    # -----------------------------------------------------
    # PRIMARY ANSWER YOK
    # -----------------------------------------------------

    if not primary_answer:
        return {
            "success": False,
            "reply": "",
            "reason": (
                "Composer primary answer üretmedi."
            ),
            "answer_type": answer_type,
            "primary_answer": primary_answer,
        }

    # -----------------------------------------------------
    # DESTEKLENMEYEN CEVAP TÜRÜ
    # -----------------------------------------------------

    if answer_type not in (
        SUPPORTED_ANSWER_TYPES
    ):
        return {
            "success": False,
            "reply": "",
            "reason": (
                "Bu cevap türü deterministic "
                "renderer tarafından henüz "
                "desteklenmiyor."
            ),
            "answer_type": answer_type,
            "primary_answer": primary_answer,
        }

    # -----------------------------------------------------
    # TYPE-SPECIFIC RENDER
    # -----------------------------------------------------

    if answer_type == "SİSTEM":
        reply = _render_system_answer(
            question,
            primary_answer,
        )

    elif answer_type == "PROSEDÜR":
        reply = _render_procedure_answer(
            question,
            primary_answer,
        )

    elif answer_type == "MESAJ":
        reply = _render_message_answer(
            question,
            primary_answer,
        )

    elif (
        answer_type
        == "STANDART / DOKÜMAN"
    ):
        reply = _render_document_answer(
            question,
            primary_answer,
        )

    elif (
        answer_type
        == "ARAYÜZ / REFERANS NOKTASI"
    ):
        reply = _render_interface_answer(
            question,
            primary_answer,
        )

    elif answer_type == "PROTOKOL":
        reply = _render_protocol_answer(
            question,
            primary_answer,
        )

    elif answer_type == "NETWORK FUNCTION":
        reply = (
            _render_network_function_answer(
                question,
                primary_answer,
            )
        )

    elif answer_type == "DEĞER / LİMİT":
        reply = _render_value_answer(
            question,
            primary_answer,
        )

    else:
        reply = ""

    if not reply:
        return {
            "success": False,
            "reply": "",
            "reason": (
                "Renderer cevap oluşturamadı."
            ),
            "answer_type": answer_type,
            "primary_answer": primary_answer,
        }

    return {
        "success": True,
        "reply": reply,
        "reason": "",
        "answer_type": answer_type,
        "primary_answer": primary_answer,
    }