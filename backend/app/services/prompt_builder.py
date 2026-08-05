from typing import Any


SYSTEM_PROMPT = """
Sen yalnızca verilen telekomünikasyon standardı parçalarına dayanarak cevap veren kaynak kontrollü bir asistansın.

Kesin kurallar:
1. Yalnızca kullanıcı promptunda verilen standart metinlerini kullan.
2. Kaynaklarda açıkça yazmayan hiçbir amacı, sebebi, özelliği veya teknik bilgiyi ekleme.
3. Tahmin yapma, yorum yapma ve genel bilginden yararlanma.
4. Liste sorulursa kaynakta geçen öğeleri doğrudan ve eksiksiz listele.
5. İngilizce kaynak metnini Türkçeye doğru ve sade biçimde çevir.
6. Aynı bilgiyi cevap içinde tekrar etme.
7. Belge kodu, sürüm veya madde numarası uydurma.
8. Kaynak listesini cevap metnine ekleme; kaynaklar backend tarafından ayrıca gösterilecek.
9. Cevabı Türkçe, kısa ve doğrudan ver.
10. Kaynaklarda cevap bulunmuyorsa yalnızca şu cümleyi yaz:
"Bu soruyu yanıtlamak için yeterli standart bilgisi bulunamadı."
""".strip()


def build_context(chunks: list[dict[str, Any]]) -> str:
    context_parts: list[str] = []

    for index, chunk in enumerate(chunks, start=1):
        metadata = chunk["metadata"]

        context_parts.append(
            "\n".join(
                [
                    f"KAYNAK {index}",
                    f"Kuruluş: {metadata.get('org', 'Bilinmiyor')}",
                    f"Belge: {metadata.get('code', 'Bilinmiyor')}",
                    f"Versiyon: {metadata.get('version', 'Bilinmiyor')}",
                    f"Madde: {metadata.get('clause', 'Bilinmiyor')}",
                    f"Metin: {chunk['text']}",
                ]
            )
        )

    return "\n\n---\n\n".join(context_parts)


def build_user_prompt(
    question: str,
    chunks: list[dict[str, Any]],
) -> str:
    context = build_context(chunks)

    return f"""
KULLANICI SORUSU:
{question}

STANDART KAYNAKLARI:
{context}

Görev:
Kullanıcının sorusuna doğrudan cevap ver.
Yalnızca yukarıdaki standart kaynaklarını kullan.
Gereksiz giriş yapma.
Cevabı 2-5 cümle arasında tut.
Kaynaklar yetersizse "Bu soruyu yanıtlamak için yeterli standart bilgisi bulunamadı." de.
""".strip()