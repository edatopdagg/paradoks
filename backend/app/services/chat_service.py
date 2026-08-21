import re
import time
from typing import Any

from app.core.config import (
    MAX_RETRIEVAL_DISTANCE,
)
from app.services.answer_composer import (
    compose_answer_evidence,
)
from app.services.answer_guard import (
    build_guard_fallback,
    build_repair_prompt,
    validate_answer,
)
from app.services.answer_renderer import (
    render_composed_answer,
)
from app.services.ollama_service import (
    OllamaServiceError,
    generate_with_ollama,
)
from app.services.prompt_builder import (
    SYSTEM_PROMPT,
    build_user_prompt,
    infer_answer_type,
)

from app.services.lexical_search_service import (
    LexicalSearchService,
)
from app.services.retriever import Retriever
from app.services.reranker_service import Reranker


# =========================================================
# PIPELINE AYARLARI
# =========================================================

RETRIEVAL_TOP_K = 3

# Normal pipeline'da Composer / Renderer / Ollama
# yalnızca en iyi iki reranked chunk'ı kullanır.
PROMPT_TOP_K = 2


# =========================================================
# CONTROLLED FALLBACK AYARLARI
# =========================================================
#
# Normal Retriever davranışını değiştirmiyoruz.
#
# İkinci retrieval yalnızca normal evidence'ın
# güvenilmez olabileceğine dair güçlü sinyal varsa
# çalışır.
# =========================================================

# Composer fallback sırasında normal soru türleri için
# sınırlı evidence kullanılır.
FALLBACK_COMPOSER_TOP_K = 4

# Doküman/RFC discovery sorularında aynı dokümanın
# birden fazla chunk'taki kanıtını Composer'ın birlikte
# görebilmesi gerekir. Bu yüzden yalnızca bu cevap türünde
# daha geniş bir lexical evidence havuzu kullanılır.
DOCUMENT_FALLBACK_COMPOSER_TOP_K = 20


# =========================================================
# DETERMINISTIC FAST-PATH TYPES
# =========================================================
#
# Bunlar genelleme testinde güvenilir davranış
# gösterdiğimiz cevap türleri.
#
# NETWORK FUNCTION özellikle yok.
# Geçerli NF benchmark/evidence olmadan deterministic
# cevap üretmeyeceğiz.
# =========================================================

FAST_PATH_TYPES = {
    "SİSTEM",
    "MESAJ",
    "PROSEDÜR",
    "STANDART / DOKÜMAN",
    "ARAYÜZ / REFERANS NOKTASI",
    "PROTOKOL",
    "DEĞER / LİMİT",
}


retriever = Retriever()
reranker = Reranker()
lexical_search = LexicalSearchService()

# =========================================================
# RESULT HELPERS
# =========================================================

def _deduplicate_results(
    results: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Aynı belge / madde / metin tekrarlarını temizler.
    """

    unique_results: list[
        dict[str, Any]
    ] = []

    seen: set[
        tuple[str, str, str, str]
    ] = set()

    for result in results:
        metadata = result.get(
            "metadata",
            {},
        )

        text = (
            result.get(
                "text"
            )
            or ""
        ).strip()

        key = (
            str(
                metadata.get(
                    "org",
                    "",
                )
            ),
            str(
                metadata.get(
                    "code",
                    "",
                )
            ),
            str(
                metadata.get(
                    "clause",
                    "",
                )
            ),
            text,
        )

        if key in seen:
            continue

        seen.add(
            key
        )

        unique_results.append(
            result
        )

    return unique_results


def _filter_available_results(
    results: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Composer / Renderer / Ollama için kullanılabilir
    kaynakları seçer.
    """

    return [
        result
        for result in results
        if result.get(
            "metadata",
            {},
        ).get(
            "status"
        )
        in {
            "available",
            "indexed",
        }
    ]


def _filter_blocked_results(
    results: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    return [
        result
        for result in results
        if result.get(
            "metadata",
            {},
        ).get(
            "status"
        )
        == "blocked"
    ]


# =========================================================
# SOURCE BUILDERS
# =========================================================

def _build_blocked_sources(
    blocked_results: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    return [
        {
            "org": result[
                "metadata"
            ].get(
                "org",
                "Bilinmiyor",
            ),
            "code": result[
                "metadata"
            ].get(
                "code",
                "Bilinmiyor",
            ),
            "source_url": result[
                "metadata"
            ].get(
                "source_url",
                "",
            ),
        }
        for result in blocked_results
    ]


def _build_sources(
    results: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Frontend'e gönderilen kaynak kartlarını metadata bazında
    tekilleştirir.

    Aynı doküman / sürüm / madde farklı chunk metinleriyle
    birkaç kez dönmüş olsa bile kullanıcı aynı kaynak kartını
    tekrar tekrar görmez.
    """

    sources: list[dict[str, Any]] = []

    seen: set[
        tuple[str, str, str, str, str]
    ] = set()

    for result in results:
        metadata = result.get(
            "metadata",
            {},
        )

        org = str(
            metadata.get(
                "org",
                "Bilinmiyor",
            )
            or "Bilinmiyor"
        )

        code = str(
            metadata.get(
                "code",
                "Bilinmiyor",
            )
            or "Bilinmiyor"
        )

        version = str(
            metadata.get(
                "version",
                "Bilinmiyor",
            )
            or "Bilinmiyor"
        )

        clause = str(
            metadata.get(
                "clause",
                "Bilinmiyor",
            )
            or "Bilinmiyor"
        )

        source_url = str(
            metadata.get(
                "source_url",
                "",
            )
            or ""
        )

        key = (
            org.casefold(),
            code.casefold(),
            version.casefold(),
            clause.casefold(),
            source_url.casefold(),
        )

        if key in seen:
            continue

        seen.add(
            key
        )

        sources.append(
            {
                "org": org,
                "code": code,
                "version": version,
                "clause": clause,
                "clause_title": metadata.get(
                    "clause_title",
                    "",
                ),
                "status": metadata.get(
                    "status",
                    "Bilinmiyor",
                ),
                "source_url": source_url,
                "distance": result.get(
                    "distance",
                    0.0,
                ),
            }
        )

    return sources


# =========================================================
# COMPOSER + RENDERER
# =========================================================

def _compose_and_render(
    question: str,
    chunks: list[dict[str, Any]],
) -> tuple[
    dict[str, Any],
    dict[str, Any],
]:
    """
    Deterministic answer path.

    Ollama kullanılmaz.
    """

    composition = (
        compose_answer_evidence(
            question=question,
            chunks=chunks,
        )
    )

    rendered = (
        render_composed_answer(
            question=question,
            composition=composition,
        )
    )

    return (
        composition,
        rendered,
    )


def _can_use_fast_path(
    composition: dict[str, Any],
    rendered: dict[str, Any],
) -> bool:
    """
    Sadece gerçekten doğrulanmış Composer çıktısı
    kullanıcıya doğrudan döner.
    """

    answer_type = str(
        composition.get(
            "answer_type",
            "",
        )
    )

    confidence = str(
        composition.get(
            "confidence",
            "low",
        )
    )

    renderer_success = bool(
        rendered.get(
            "success",
            False,
        )
    )

    reply = str(
        rendered.get(
            "reply",
            "",
        )
        or ""
    ).strip()

    return (
        answer_type
        in FAST_PATH_TYPES
        and confidence == "high"
        and renderer_success
        and bool(reply)
    )


# =========================================================
# SUSPICIOUS ANSWER DETECTION
# =========================================================

def _value_answer_echoes_question(
    question: str,
    primary_answer: str,
) -> bool:
    """
    DEĞER / LİMİT sorularında bir identifier'ın içindeki
    sayı yanlışlıkla cevap olarak seçilmiş olabilir.

    Örnek:

        Soru:
            E.164 numarası en fazla kaç basamak?

        Yanlış candidate:
            164 digit

    Buradaki 164 zaten sorudaki E.164 identifier'ından
    geliyor. Bu nedenle ikinci retrieval gerekir.

    Ancak:
        15 digits

    sorunun içinde geçmediği için şüpheli sayılmaz.
    """

    answer_numbers = re.findall(
        r"\d+(?:\.\d+)?",
        primary_answer
        or "",
    )

    if not answer_numbers:
        return False

    normalized_question = (
        question
        or ""
    ).casefold()

    return any(
        number
        in normalized_question
        for number in answer_numbers
    )

def _precision_fallback_phrases(
    question: str,
) -> list[str]:
    """
    Bazı teknik intent'lerde semantic retrieval yerine
    standartta gerçekten geçen ayırt edici ifadeleri
    lexical second-pass için kullanır.

    Burada cevap hard-code edilmez.
    Yalnızca evidence bulmaya yarayan standart ifadeleri
    tanımlarız.
    """

    normalized_question = (
        question
        or ""
    ).casefold()

    # -----------------------------------------------------
    # SERVICE REQUEST
    # -----------------------------------------------------

    service_request_intent = (
        "service request"
        in normalized_question
        or (
            "uplink"
            in normalized_question
            and any(
                value
                in normalized_question
                for value in (
                    "yeniden etkinleştir",
                    "tekrar etkinleştir",
                    "tekrar aktif",
                    "activate",
                    "reactivate",
                )
            )
        )
    )

    if service_request_intent:
        return [
            "Service Request procedure is used",
        ]

    # -----------------------------------------------------
    # HTTP/3 DOCUMENT / RFC
    # -----------------------------------------------------

    http3_intent = (
        "http/3"
        in normalized_question
        or "http3"
        in normalized_question
    )

    specialized_http3_subject = any(
        value
        in normalized_question
        for value in (
            "websocket",
            "qpack",
        )
    )

    if (
        http3_intent
        and not specialized_http3_subject
        and any(
            value
            in normalized_question
            for value in (
                "rfc",
                "standart",
                "standard",
                "doküman",
                "document",
                "tanımlan",
                "defined",
            )
        )
    ):
        return [
            "This document defines HTTP/3",
        ]

    # -----------------------------------------------------
    # QUIC LOSS / RECOVERY / CONGESTION CONTROL
    # -----------------------------------------------------

    if (
        "quic"
        in normalized_question
        and any(
            value
            in normalized_question
            for value in (
                "kayıp",
                "loss",
                "congestion",
                "recovery",
            )
        )
    ):
        return [
            (
                "This document describes loss detection "
                "and congestion control mechanisms for QUIC"
            ),
        ]

    # -----------------------------------------------------
    # CELL BROADCAST WARNING CANCELLATION
    # -----------------------------------------------------

    cell_broadcast_intent = any(
        value
        in normalized_question
        for value in (
            "cell broadcast",
            "warning message",
            "uyarı mesaj",
        )
    )

    cancellation_intent = any(
        value
        in normalized_question
        for value in (
            "iptal",
            "cancel",
            "stop",
            "durdur",
        )
    )

    if (
        cell_broadcast_intent
        and cancellation_intent
    ):
        return [
            (
                "The cancel warning message delivery "
                "procedure takes place"
            ),
        ]

    return []

def _is_reference_point_question(
    question: str,
) -> bool:
    value = (
        question
        or ""
    ).casefold()

    return (
        "referans nokta"
        in value
        or
        "reference point"
        in value
    )


def _reference_point_fts_query(
    question: str,
) -> str | None:
    """
    Sorudaki iki endpoint'ten genel bir
    reference-point FTS sorgusu üretir.

    N1/N3/N4/N11/N12 gibi cevaplar burada
    bilinmez veya hard-code edilmez.
    """

    tokens = re.findall(
        r"\b(?:NG-RAN|[A-Z]{2,}(?:-[A-Z0-9]+)*)\b",
        question or "",
    )

    excluded = {
        "5G",
        "5GS",
        "TS",
        "TR",
        "RFC",
        "REFERENCE",
        "POINT",
        "INTERFACE",
    }

    endpoints: list[str] = []

    for token in tokens:
        if token in excluded:
            continue

        if token not in endpoints:
            endpoints.append(
                token
            )

    if len(endpoints) < 2:
        return None

    first = endpoints[0]
    second = endpoints[1]

    # Standartlarda erişim tarafı bazen
    # NG-RAN, RAN veya (R)AN yazılabiliyor.
    if first in {
        "NG-RAN",
        "RAN",
    }:
        return (
            '"reference point between" '
            f'AND "{second}"'
        )

    if second in {
        "NG-RAN",
        "RAN",
    }:
        return (
            '"reference point between" '
            f'AND "{first}"'
        )

    return (
        '"reference point" '
        f'AND "{first}" '
        f'AND "{second}"'
    )



def _is_document_question(
    question: str,
) -> bool:
    """
    Kullanıcının doğrudan bir standart / RFC / doküman
    kimliği sorduğu soruları ayırır.

    Cevap numarası burada bilinmez; yalnızca cevap türü
    belirlenir.
    """

    return (
        infer_answer_type(
            question
        )
        == "STANDART / DOKÜMAN"
    )

def _needs_targeted_fallback(
    question: str,
    composition: dict[str, Any],
    rendered: dict[str, Any],
) -> bool:
    """
    Global retrieval ayarlarını büyütmek yerine,
    yalnızca gerçekten ihtiyaç duyulan sorularda
    ikinci retrieval çalıştırır.
    """
    if _is_reference_point_question(
        question
    ):
        return True

    precision_phrases = (
        _precision_fallback_phrases(
            question
        )
    )

    if precision_phrases:
        return True

    # Standart / RFC / doküman kimliği sorularında
    # normal semantic retrieval doğru cevabı verse bile
    # başka bir dokümanın References/Overview maddesine
    # kayma riski yüksek. Precision route'u olmayan
    # document soruları lexical document discovery'ye gider.
    if _is_document_question(
        question
    ):
        return True

    answer_type = str(
        composition.get(
            "answer_type",
            "",
        )
    )

    confidence = str(
        composition.get(
            "confidence",
            "low",
        )
    )

    primary_answer = str(
        composition.get(
            "primary_answer",
            "",
        )
        or ""
    ).strip()

    renderer_success = bool(
        rendered.get(
            "success",
            False,
        )
    )

    # -----------------------------------------------------
    # VALUE IDENTIFIER ECHO
    # -----------------------------------------------------

    if (
        answer_type
        == "DEĞER / LİMİT"
        and primary_answer
        and _value_answer_echoes_question(
            question=question,
            primary_answer=primary_answer,
        )
    ):
        return True

    # -----------------------------------------------------
    # LOW / MEDIUM CONFIDENCE
    # -----------------------------------------------------

    if (
        answer_type == "DEĞER / LİMİT"
        and (
            confidence != "high"
            or not renderer_success
        )
    ):
        return True

    return False


# =========================================================
# TARGETED SECOND-PASS RETRIEVAL
# =========================================================

def _document_fallback_candidates(
    question: str,
) -> list[dict[str, Any]]:
    """
    Standart / RFC sorularında QueryNormalizer'ın teknik
    expansion'larını FTS5 üzerinde arar.

    Önemli fark:
    - Orijinal doğal dil sorusu yerine teknik expansion'lar
      tercih edilir.
    - Sonuçlar global bm25 ile yeniden sıralanmaz.
      Variant sırası korunur; Composer böylece aynı
      dokümana ait tekrarlayan kanıtları birlikte görür.
    - Cevap numarası hard-code edilmez.
    """

    search_queries = (
        retriever
        .query_normalizer
        .normalize(
            question,
            max_variants=4,
        )
    )

    phrase_queries = (
        search_queries[1:]
        if len(search_queries) > 1
        else search_queries
    )

    if not phrase_queries:
        return []

    print(
        "[FALLBACK] Document discovery sorguları:",
        phrase_queries,
    )

    candidates: list[
        dict[str, Any]
    ] = []

    seen_chunk_ids: set[str] = set()

    for phrase in phrase_queries:
        results = (
            lexical_search.search_phrase(
                phrase=phrase,
                limit=10,
            )
        )

        print(
            f"[FALLBACK] Document hit "
            f"'{phrase}': "
            f"{len(results)}"
        )

        for result in results:
            chunk_id = str(
                result.get(
                    "chunk_id",
                    "",
                )
            )

            if (
                chunk_id
                and chunk_id in seen_chunk_ids
            ):
                continue

            if chunk_id:
                seen_chunk_ids.add(
                    chunk_id
                )

            candidates.append(
                result
            )

    print(
        "[FALLBACK] Document toplam unique aday:",
        len(candidates),
    )

    return candidates[
        :DOCUMENT_FALLBACK_COMPOSER_TOP_K
    ]


def _parse_primary_document_identity(
    primary_answer: str,
) -> tuple[str, str] | None:
    """
    Composer'ın doküman cevabını Chroma metadata
    kimliğine çevirir.

    Örnek:
        RFC 9204
            -> ("IETF", "9204")

        3GPP TS 23.502
            -> ("3GPP", "TS 23.502")
    """

    answer = (
        primary_answer
        or ""
    ).strip()

    if not answer:
        return None

    rfc_match = re.fullmatch(
        r"RFC\s+(\d+)",
        answer,
        flags=re.IGNORECASE,
    )

    if rfc_match:
        return (
            "IETF",
            rfc_match.group(1),
        )

    spec_match = re.fullmatch(
        r"(3GPP|ETSI)\s+(TS|TR)\s+([\d.]+)",
        answer,
        flags=re.IGNORECASE,
    )

    if spec_match:
        return (
            spec_match.group(1).upper(),
            (
                f"{spec_match.group(2).upper()} "
                f"{spec_match.group(3)}"
            ),
        )

    return None


def _document_source_quality_score(
    result: dict[str, Any],
) -> float:
    """
    Dokümanın kendisini tanımlayan maddeleri kaynak kartında
    öne çıkarır.

    Scope / Introduction / Overview ve "this/present document"
    türü self-definition ifadeleri güçlüdür. References bölümleri
    ise doküman kimliğini göstermek için daha zayıf kanıttır.
    """

    metadata = result.get(
        "metadata",
        {},
    )

    clause_title = str(
        metadata.get(
            "clause_title",
            "",
        )
        or ""
    ).casefold()

    text = str(
        result.get(
            "text",
            "",
        )
        or ""
    ).casefold()

    score = 0.0

    if "scope" in clause_title:
        score += 10.0

    if any(
        value in clause_title
        for value in (
            "introduction",
            "overview",
        )
    ):
        score += 7.0

    if "reference" in clause_title:
        score -= 10.0

    if re.search(
        r"\b(?:this document|the present document)\s+"
        r"(?:defines|specifies|describes)\b",
        text,
        flags=re.IGNORECASE,
    ):
        score += 10.0

    return score


def _fetch_primary_document_sources(
    question: str,
    primary_answer: str,
    limit: int = 4,
) -> list[dict[str, Any]]:
    """
    Composer doğru doküman kimliğini cross-reference
    üzerinden bulmuş olsa bile lexical candidate havuzunda
    hedef dokümanın kendi chunk'ları bulunmayabilir.

    Bu durumda hedef dokümanı metadata ile doğrudan Chroma'dan
    bulur ve yalnızca kaynak gösterimi için en ilgili chunk'ları
    seçer.

    Hedef doküman DB'de yoksa boş liste döner.
    Örneğin RFC 8999 yerel indexte yoksa mevcut cross-reference
    kaynağı kullanılmaya devam eder.
    """

    identity = (
        _parse_primary_document_identity(
            primary_answer
        )
    )

    if identity is None:
        return []

    org, code = identity

    try:
        result = (
            retriever.collection.get(
                where={
                    "$and": [
                        {"org": org},
                        {"code": code},
                    ]
                },
                limit=40,
                include=[
                    "documents",
                    "metadatas",
                ],
            )
        )
    except Exception as error:
        print(
            "[SOURCE] Primary document lookup failed:",
            error,
        )
        return []

    candidates: list[
        dict[str, Any]
    ] = []

    for (
        chunk_id,
        document,
        metadata,
    ) in zip(
        result.get(
            "ids",
            [],
        ),
        result.get(
            "documents",
            [],
        ),
        result.get(
            "metadatas",
            [],
        ),
    ):
        clean_text = (
            document
            or ""
        ).strip()

        clean_metadata = (
            metadata
            or {}
        )

        if not clean_text:
            continue

        if clean_metadata.get(
            "status"
        ) not in {
            "available",
            "indexed",
        }:
            continue

        candidates.append(
            {
                "chunk_id": chunk_id,
                "text": clean_text,
                "metadata": clean_metadata,
                "distance": 0.0,
            }
        )

    candidates = (
        _deduplicate_results(
            candidates
        )
    )

    if not candidates:
        return []

    # Doküman kimliği sorularında References maddesinden ziyade
    # Scope / Introduction / Overview gibi dokümanın kendi kapsamını
    # tanımlayan bölümleri tercih et.
    quality_candidates = [
        candidate
        for candidate in candidates
        if _document_source_quality_score(
            candidate
        ) > 0.0
    ]

    rerank_pool = (
        quality_candidates
        if quality_candidates
        else candidates
    )

    if len(rerank_pool) == 1:
        return rerank_pool[:limit]

    try:
        ranked = reranker.rerank(
            query=question,
            candidates=rerank_pool,
            top_k=min(
                limit,
                len(rerank_pool),
            ),
        )

        if ranked:
            return sorted(
                ranked,
                key=_document_source_quality_score,
                reverse=True,
            )[:limit]

    except Exception as error:
        print(
            "[SOURCE] Primary document rerank failed:",
            error,
        )

    return sorted(
        rerank_pool,
        key=_document_source_quality_score,
        reverse=True,
    )[:limit]


def _select_document_source_results(
    results: list[dict[str, Any]],
    primary_answer: str,
    question: str = "",
    limit: int = 4,
) -> list[dict[str, Any]]:
    """
    Document Composer'ın seçtiği ana cevabı kullanıcıya
    gösterilen kaynaklarla hizalar.

    Öncelik:
    1. Candidate havuzunda hedef dokümanın kendi chunk'ı.
    2. Hedef dokümanı Chroma metadata'sından doğrudan bulma.
    3. Hedef dokümanı açıkça referanslayan cross-reference chunk'ı.
    4. Mevcut candidate havuzu.

    Böylece:
        cevap = 3GPP TS 23.502
    ise mümkün olduğunda kaynak kartında da TS 23.502 gösterilir.

    RFC 8999 gibi hedef doküman DB'de yoksa cross-reference
    kanıtı korunur.
    """

    answer = (
        primary_answer
        or ""
    ).strip()

    if not answer:
        return results[:limit]

    identity = (
        _parse_primary_document_identity(
            answer
        )
    )

    direct_matches: list[
        dict[str, Any]
    ] = []

    if identity is not None:
        expected_org, expected_code = (
            identity
        )

        for result in results:
            metadata = result.get(
                "metadata",
                {},
            )

            org = str(
                metadata.get(
                    "org",
                    "",
                )
                or ""
            ).strip()

            code = str(
                metadata.get(
                    "code",
                    "",
                )
                or ""
            ).strip()

            if (
                org.casefold()
                == expected_org.casefold()
                and code.casefold()
                == expected_code.casefold()
            ):
                direct_matches.append(
                    result
                )

    # Kaynak paneli için hedef dokümanın kendi Scope / Introduction
    # gibi daha açıklayıcı maddelerini DB'den çekmeyi önce dene.
    # Böylece fallback havuzunda yalnızca References maddesi varsa
    # kullanıcıya onu dört kez göstermek yerine daha anlamlı kaynak
    # kartı sunulur.
    if question:
        hydrated_matches = (
            _fetch_primary_document_sources(
                question=question,
                primary_answer=answer,
                limit=limit,
            )
        )

        if hydrated_matches:
            print(
                "[SOURCE] Primary document hydrated:",
                answer,
                "| chunk:",
                len(hydrated_matches),
            )
            return hydrated_matches

    if direct_matches:
        return _deduplicate_results(
            direct_matches
        )[:limit]

    # Cross-reference fallback:
    # Hedef dokümanın kendisi indexte olmayabilir.
    answer_tokens = [
        answer,
    ]

    rfc_match = re.fullmatch(
        r"RFC\s+(\d+)",
        answer,
        flags=re.IGNORECASE,
    )

    if rfc_match:
        answer_tokens.append(
            f"RFC{rfc_match.group(1)}"
        )

    referenced_matches = [
        result
        for result in results
        if any(
            token.casefold()
            in str(
                result.get(
                    "text",
                    "",
                )
                or ""
            ).casefold()
            for token in answer_tokens
        )
    ]

    if referenced_matches:
        return referenced_matches[:limit]

    return results[:limit]

def _targeted_fallback_retrieval(
    question: str,
) -> list[dict[str, Any]]:
    """
    Kontrollü lexical second-pass retrieval.

    Normal semantic Retriever'a dokunmaz.

    QueryNormalizer'ın ürettiği teknik İngilizce
    varyantları SQLite FTS5 üzerinde phrase search
    olarak arar.

    Örnek:
        E.164 number maximum length
        document defines version 1 of QUIC
    """
    reference_query = (
        _reference_point_fts_query(
            question
        )
    )

    if reference_query:
        print(
            "[FALLBACK] Reference-point FTS:",
            reference_query,
        )

        reference_results = (
            lexical_search.search_query(
                query=reference_query,
                limit=20,
            )
        )

        if reference_results:
            print(
                "[FALLBACK] Reference-point aday:",
                len(reference_results),
            )

            return reference_results

    precision_phrases = (
        _precision_fallback_phrases(
            question
        )
    )

    if precision_phrases:
        phrase_queries = (
            precision_phrases
        )

        print(
            "[FALLBACK] Precision lexical route:",
            phrase_queries,
        )

    elif _is_document_question(
        question
    ):
        return (
            _document_fallback_candidates(
                question
            )
        )

    else:
        search_queries = (
            retriever
            .query_normalizer
            .normalize(
                question,
                max_variants=4,
            )
        )

        # Orijinal kullanıcı sorusunu değil,
        # teknik expansion'ları lexical fallback'te kullan.
        phrase_queries = (
            search_queries[1:]
            if len(search_queries) > 1
            else []
        )

    if not phrase_queries:
        return []

    print(
        "[FALLBACK] FTS5 phrase sorguları:",
        phrase_queries,
    )

    candidates: list[
        dict[str, Any]
    ] = []

    seen_chunk_ids: set[str] = set()

    for phrase in phrase_queries:
        results = (
            lexical_search.search_phrase(
                phrase=phrase,
                limit=10,
            )
        )

        print(
            f"[FALLBACK] FTS5 hit "
            f"'{phrase}': "
            f"{len(results)}"
        )

        for result in results:
            chunk_id = str(
                result.get(
                    "chunk_id",
                    "",
                )
            )

            if (
                chunk_id
                and chunk_id
                in seen_chunk_ids
            ):
                continue

            if chunk_id:
                seen_chunk_ids.add(
                    chunk_id
                )

            candidates.append(
                result
            )

    # FTS5 bm25 için daha küçük / daha negatif
    # lexical_score daha güçlü sonuçtur.
    candidates.sort(
        key=lambda item: float(
            item.get(
                "lexical_score",
                0.0,
            )
        )
    )

    print(
        "[FALLBACK] FTS5 toplam unique aday:",
        len(candidates),
    )

    return candidates[
        :FALLBACK_COMPOSER_TOP_K
    ]

# =========================================================
# PERFORMANCE PRINTER
# =========================================================

def _print_performance(
    retrieval_time: float,
    reranker_time: float,
    composer_time: float,
    fallback_time: float,
    prompt_time: float,
    ollama_time: float,
    guard_time: float,
    repair_used: bool,
    deterministic_used: bool,
    total_time: float,
) -> None:
    print()

    print(
        "=" * 50
    )

    print(
        "[PERF] Paradoks Pipeline"
    )

    print(
        f"[PERF] Retrieval: "
        f"{retrieval_time:.2f} sn"
    )

    print(
        f"[PERF] Reranker: "
        f"{reranker_time:.2f} sn"
    )

    print(
        f"[PERF] Composer + Renderer: "
        f"{composer_time:.4f} sn"
    )

    print(
        f"[PERF] Targeted fallback: "
        f"{fallback_time:.2f} sn"
    )

    print(
        f"[PERF] Prompt: "
        f"{prompt_time:.4f} sn"
    )

    print(
        f"[PERF] Ollama: "
        f"{ollama_time:.2f} sn"
    )

    print(
        f"[PERF] Answer Guard CPU: "
        f"{guard_time:.4f} sn"
    )

    print(
        "[PERF] Deterministic cevap:",
        (
            "EVET"
            if deterministic_used
            else "HAYIR"
        ),
    )

    print(
        "[PERF] Guard repair:",
        (
            "EVET"
            if repair_used
            else "HAYIR"
        ),
    )

    print(
        f"[PERF] Total: "
        f"{total_time:.2f} sn"
    )

    print(
        "=" * 50
    )

    print()


# =========================================================
# MAIN PIPELINE
# =========================================================

def generate_reply(
    message: str,
) -> dict[str, Any]:
    """
    Paradoks soru-cevap pipeline'ı.

    Akış:

    1. Normal retrieval
    2. Status filtreleme
    3. Duplicate temizleme
    4. Reranker
    5. Composer
    6. Renderer
    7. Güvenilir deterministic cevap varsa direkt dön
    8. Gerekirse controlled second-pass retrieval
    9. Hâlâ deterministic cevap yoksa Ollama
    10. Answer Guard
    11. Gerekirse tek repair denemesi
    12. Kaynak metadata'larını döndür
    """

    total_start = (
        time.perf_counter()
    )

    reranker_time = 0.0
    composer_time = 0.0
    fallback_time = 0.0
    prompt_time = 0.0
    ollama_time = 0.0
    guard_time = 0.0

    repair_used = False
    deterministic_used = False

    # -----------------------------------------------------
    # NORMAL RETRIEVAL
    # -----------------------------------------------------

    retrieval_start = (
        time.perf_counter()
    )

    results = retriever.search(
        query=message,
        top_k=RETRIEVAL_TOP_K,
    )

    retrieval_time = (
        time.perf_counter()
        - retrieval_start
    )

    available_results = (
        _filter_available_results(
            results
        )
    )

    blocked_results = (
        _filter_blocked_results(
            results
        )
    )

    available_results = (
        _deduplicate_results(
            available_results
        )
    )

    print(
        "[PIPELINE] Retrieval aday:",
        len(results),
    )

    print(
        "[PIPELINE] Kullanılabilir unique aday:",
        len(available_results),
    )

    # -----------------------------------------------------
    # NO SOURCES
    # -----------------------------------------------------

    if not available_results:
        total_time = (
            time.perf_counter()
            - total_start
        )

        _print_performance(
            retrieval_time=(
                retrieval_time
            ),
            reranker_time=0.0,
            composer_time=0.0,
            fallback_time=0.0,
            prompt_time=0.0,
            ollama_time=0.0,
            guard_time=0.0,
            repair_used=False,
            deterministic_used=False,
            total_time=total_time,
        )

        return {
            "reply": (
                "Bu soruyu yanıtlamak için "
                "erişilebilir bir standart "
                "maddesi bulunamadı."
            ),
            "sources": [],
            "blocked_sources": (
                _build_blocked_sources(
                    blocked_results
                )
            ),
        }

    # -----------------------------------------------------
    # NORMAL RERANKER
    # -----------------------------------------------------

    reranker_start = (
        time.perf_counter()
    )

    if len(
        available_results
    ) == 1:
        reranked_results = (
            available_results
        )

    else:
        reranked_results = (
            reranker.rerank(
                query=message,
                candidates=(
                    available_results
                ),
                top_k=PROMPT_TOP_K,
            )
        )

    reranker_time = (
        time.perf_counter()
        - reranker_start
    )

    prompt_results = (
        reranked_results[
            :PROMPT_TOP_K
        ]
    )

    print(
        "[PIPELINE] Normal evidence chunk:",
        len(prompt_results),
    )

    # -----------------------------------------------------
    # NORMAL COMPOSER + RENDERER
    # -----------------------------------------------------

    composer_start = (
        time.perf_counter()
    )

    (
        composition,
        rendered,
    ) = _compose_and_render(
        question=message,
        chunks=prompt_results,
    )

    composer_time += (
        time.perf_counter()
        - composer_start
    )

    print(
        "[COMPOSER] Answer type:",
        composition.get(
            "answer_type",
        ),
    )

    print(
        "[COMPOSER] Primary:",
        composition.get(
            "primary_answer",
        ),
    )

    print(
        "[COMPOSER] Confidence:",
        composition.get(
            "confidence",
        ),
    )

    # -----------------------------------------------------
    # TARGETED FALLBACK GEREKİYOR MU?
    # -----------------------------------------------------

    fallback_required = (
        _needs_targeted_fallback(
            question=message,
            composition=composition,
            rendered=rendered,
        )
    )

    # -----------------------------------------------------
    # NORMAL FAST PATH
    # -----------------------------------------------------

    if (
        not fallback_required
        and _can_use_fast_path(
            composition,
            rendered,
        )
    ):
        deterministic_used = True

        reply = str(
            rendered.get(
                "reply",
                "",
            )
        )

        total_time = (
            time.perf_counter()
            - total_start
        )

        _print_performance(
            retrieval_time=(
                retrieval_time
            ),
            reranker_time=(
                reranker_time
            ),
            composer_time=(
                composer_time
            ),
            fallback_time=0.0,
            prompt_time=0.0,
            ollama_time=0.0,
            guard_time=0.0,
            repair_used=False,
            deterministic_used=True,
            total_time=total_time,
        )

        return {
            "reply": reply,
            "sources": (
                _build_sources(
                    prompt_results
                )
            ),
            "blocked_sources": (
                _build_blocked_sources(
                    blocked_results
                )
            ),
        }

    # -----------------------------------------------------
    # CONTROLLED SECOND PASS
    # -----------------------------------------------------

    fallback_prompt_results: list[
        dict[str, Any]
    ] = []

    fallback_composition: dict[
        str,
        Any
    ] = {}

    fallback_rendered: dict[
        str,
        Any
    ] = {}

    if fallback_required:
        print(
            "[FALLBACK] Targeted second-pass retrieval başlıyor."
        )

        fallback_start = (
            time.perf_counter()
        )

        fallback_results = (
            _targeted_fallback_retrieval(
                message
            )
        )

        fallback_time += (
            time.perf_counter()
            - fallback_start
        )

        fallback_prompt_results = (
            fallback_results[
                :FALLBACK_COMPOSER_TOP_K
            ]
        )

        fallback_composer_results = (
            fallback_prompt_results
        )

        if (
            str(
                composition.get(
                    "answer_type",
                    "",
                )
            )
            == "STANDART / DOKÜMAN"
        ):
            fallback_composer_results = (
                fallback_results[
                    :DOCUMENT_FALLBACK_COMPOSER_TOP_K
                ]
            )

        print(
            "[FALLBACK] Composer evidence chunk:",
            len(
                fallback_composer_results
            ),
        )

        if fallback_composer_results:
            fallback_composer_start = (
                time.perf_counter()
            )

            (
                fallback_composition,
                fallback_rendered,
            ) = _compose_and_render(
                question=message,
                chunks=(
                    fallback_composer_results
                ),
            )

            composer_time += (
                time.perf_counter()
                - fallback_composer_start
            )

            print(
                "[FALLBACK COMPOSER] Primary:",
                fallback_composition.get(
                    "primary_answer",
                ),
            )

            print(
                "[FALLBACK COMPOSER] Confidence:",
                fallback_composition.get(
                    "confidence",
                ),
            )

            if _can_use_fast_path(
                fallback_composition,
                fallback_rendered,
            ):
                deterministic_used = True

                reply = str(
                    fallback_rendered.get(
                        "reply",
                        "",
                    )
                )

                total_time = (
                    time.perf_counter()
                    - total_start
                )

                _print_performance(
                    retrieval_time=(
                        retrieval_time
                    ),
                    reranker_time=(
                        reranker_time
                    ),
                    composer_time=(
                        composer_time
                    ),
                    fallback_time=(
                        fallback_time
                    ),
                    prompt_time=0.0,
                    ollama_time=0.0,
                    guard_time=0.0,
                    repair_used=False,
                    deterministic_used=True,
                    total_time=total_time,
                )

                source_results = (
                    fallback_prompt_results
                )

                if (
                    str(
                        fallback_composition.get(
                            "answer_type",
                            "",
                        )
                    )
                    == "STANDART / DOKÜMAN"
                ):
                    source_results = (
                        _select_document_source_results(
                            fallback_composer_results,
                            str(
                                fallback_composition.get(
                                    "primary_answer",
                                    "",
                                )
                            ),
                            question=message,
                        )
                    )

                return {
                    "reply": reply,
                    "sources": (
                        _build_sources(
                            source_results
                        )
                    ),
                    "blocked_sources": (
                        _build_blocked_sources(
                            blocked_results
                        )
                    ),
                }

    # -----------------------------------------------------
    # LLM EVIDENCE SELECTION
    # -----------------------------------------------------
    #
    # Targeted fallback daha iyi bir evidence seti üretmiş
    # ama deterministic confidence yeterli olmamışsa,
    # Ollama'nın da bu daha güçlü evidence'ı görmesine
    # izin ver.
    # -----------------------------------------------------

    llm_results = (
        prompt_results
    )

    if (
        fallback_prompt_results
        and str(
            fallback_composition.get(
                "confidence",
                "low",
            )
        )
        in {
            "medium",
            "high",
        }
    ):
        if (
            str(
                fallback_composition.get(
                    "answer_type",
                    "",
                )
            )
            == "STANDART / DOKÜMAN"
        ):
            llm_results = (
                _select_document_source_results(
                    fallback_composer_results,
                    str(
                        fallback_composition.get(
                            "primary_answer",
                            "",
                        )
                    ),
                    question=message,
                    limit=PROMPT_TOP_K,
                )
            )

        else:
            llm_results = (
                fallback_prompt_results[
                    :PROMPT_TOP_K
                ]
            )

    # -----------------------------------------------------
    # PROMPT
    # -----------------------------------------------------

    prompt_start = (
        time.perf_counter()
    )

    user_prompt = (
        build_user_prompt(
            question=message,
            chunks=llm_results,
        )
    )

    prompt_time = (
        time.perf_counter()
        - prompt_start
    )

    print(
        "[PIPELINE] Ollama prompt chunk:",
        len(llm_results),
    )

    print(
        "[PIPELINE] User prompt karakter:",
        len(user_prompt),
    )

    # -----------------------------------------------------
    # OLLAMA
    # -----------------------------------------------------

    ollama_start = (
        time.perf_counter()
    )

    try:
        reply = (
            generate_with_ollama(
                system_prompt=(
                    SYSTEM_PROMPT
                ),
                user_prompt=(
                    user_prompt
                ),
            )
        )

        ollama_time += (
            time.perf_counter()
            - ollama_start
        )

    except OllamaServiceError as error:
        ollama_time += (
            time.perf_counter()
            - ollama_start
        )

        total_time = (
            time.perf_counter()
            - total_start
        )

        _print_performance(
            retrieval_time=(
                retrieval_time
            ),
            reranker_time=(
                reranker_time
            ),
            composer_time=(
                composer_time
            ),
            fallback_time=(
                fallback_time
            ),
            prompt_time=(
                prompt_time
            ),
            ollama_time=(
                ollama_time
            ),
            guard_time=0.0,
            repair_used=False,
            deterministic_used=False,
            total_time=total_time,
        )

        return {
            "reply": (
                f"Yanıt üretilemedi: "
                f"{error}"
            ),
            "sources": [],
            "blocked_sources": (
                _build_blocked_sources(
                    blocked_results
                )
            ),
        }

    # -----------------------------------------------------
    # ANSWER GUARD
    # -----------------------------------------------------

    guard_start = (
        time.perf_counter()
    )

    validation = (
        validate_answer(
            question=message,
            reply=reply,
            chunks=llm_results,
        )
    )

    guard_time += (
        time.perf_counter()
        - guard_start
    )

    print(
        "[ANSWER GUARD] İlk cevap:",
        (
            "PASS"
            if validation[
                "valid"
            ]
            else "FAIL"
        ),
    )

    if not validation[
        "valid"
    ]:
        print(
            "[ANSWER GUARD] Sebep:",
            validation.get(
                "reason",
                "",
            ),
        )

        print(
            "[ANSWER GUARD] Beklenen tür:",
            validation.get(
                "answer_type",
                "",
            ),
        )

        print(
            "[ANSWER GUARD] Evidence:",
            validation.get(
                "evidence_terms",
                [],
            ),
        )

        repair_used = True

        # -------------------------------------------------
        # SINGLE REPAIR
        # -------------------------------------------------

        repair_prompt = (
            build_repair_prompt(
                question=message,
                bad_reply=reply,
                chunks=llm_results,
                validation=validation,
            )
        )

        repair_start = (
            time.perf_counter()
        )

        try:
            repaired_reply = (
                generate_with_ollama(
                    system_prompt=(
                        SYSTEM_PROMPT
                    ),
                    user_prompt=(
                        repair_prompt
                    ),
                )
            )

            ollama_time += (
                time.perf_counter()
                - repair_start
            )

        except OllamaServiceError:
            ollama_time += (
                time.perf_counter()
                - repair_start
            )

            repaired_reply = ""

        # -------------------------------------------------
        # SECOND VALIDATION
        # -------------------------------------------------

        if repaired_reply:
            second_guard_start = (
                time.perf_counter()
            )

            second_validation = (
                validate_answer(
                    question=message,
                    reply=repaired_reply,
                    chunks=llm_results,
                )
            )

            guard_time += (
                time.perf_counter()
                - second_guard_start
            )

            print(
                "[ANSWER GUARD] Repair cevap:",
                (
                    "PASS"
                    if second_validation[
                        "valid"
                    ]
                    else "FAIL"
                ),
            )

            if second_validation[
                "valid"
            ]:
                reply = (
                    repaired_reply
                )

            else:
                print(
                    "[ANSWER GUARD] Repair sebep:",
                    second_validation.get(
                        "reason",
                        "",
                    ),
                )

                reply = (
                    build_guard_fallback(
                        second_validation
                    )
                )

        else:
            reply = (
                build_guard_fallback(
                    validation
                )
            )

    # -----------------------------------------------------
    # SOURCES
    # -----------------------------------------------------

    sources = (
        _build_sources(
            llm_results
        )
    )

    blocked_sources = (
        _build_blocked_sources(
            blocked_results
        )
    )

    # -----------------------------------------------------
    # TOTAL
    # -----------------------------------------------------

    total_time = (
        time.perf_counter()
        - total_start
    )

    _print_performance(
        retrieval_time=(
            retrieval_time
        ),
        reranker_time=(
            reranker_time
        ),
        composer_time=(
            composer_time
        ),
        fallback_time=(
            fallback_time
        ),
        prompt_time=(
            prompt_time
        ),
        ollama_time=(
            ollama_time
        ),
        guard_time=(
            guard_time
        ),
        repair_used=(
            repair_used
        ),
        deterministic_used=(
            deterministic_used
        ),
        total_time=(
            total_time
        ),
    )

    return {
        "reply": reply,
        "sources": sources,
        "blocked_sources": blocked_sources,
    }