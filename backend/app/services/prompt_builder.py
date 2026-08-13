from typing import Any


SYSTEM_PROMPT = """
Sen, yalnızca verilen telekomünikasyon standardı parçalarına dayanarak cevap veren kaynak kontrollü bir asistansın.

Kurallar:
- Yalnızca verilen standart metinlerini kullan.
- Kaynakta açıkça bulunmayan bilgi ekleme, tahmin veya yorum yapma.
- İngilizce kaynakları doğru ve sade Türkçeyle aktar.
- Aynı bilgiyi tekrar etme.
- Belge, sürüm veya madde numarası uydurma.
- Kaynak listesini cevaba yazma; backend ayrıca gösterecek.
- Cevabı kısa, doğrudan ve Türkçe ver.
- Yeterli bilgi yoksa yalnızca:
"Bu soruyu yanıtlamak için yeterli standart bilgisi bulunamadı."
""".strip()


def build_context(
    chunks: list[dict[str, Any]],
) -> str:
    context_parts: list[str] = []

    for chunk in chunks:
        metadata = chunk["metadata"]

        code = metadata.get(
            "code",
            "Bilinmiyor",
        )

        clause = metadata.get(
            "clause",
            "Bilinmiyor",
        )

        text = (
            chunk.get("text")
            or ""
        ).strip()

        context_parts.append(
            "\n".join(
                [
                    f"[{code} | Madde {clause}]",
                    text,
                ]
            )
        )

    return "\n\n".join(
        context_parts
    )


def build_user_prompt(
    question: str,
    chunks: list[dict[str, Any]],
) -> str:
    context = build_context(
        chunks
    )

    return f"""
SORU:
{question}

KAYNAKLAR:
{context}

Yalnızca bu kaynaklara dayanarak 2-4 cümlelik doğrudan bir cevap ver.
""".strip()