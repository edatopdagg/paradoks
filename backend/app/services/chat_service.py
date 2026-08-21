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

FALLBACK_CHROMA_RESULTS_PER_QUERY = 12

# Her teknik query varyantından alınabilecek
# en fazla candidate.
FALLBACK_KEEP_PER_QUERY = 5

# İkinci retrieval sonrasında reranker'a
# gönderilecek maksimum candidate.
FALLBACK_RERANK_TOP_K = 6

# Composer fallback sırasında biraz daha fazla
# evidence görebilir.
#
# Bu normal pipeline'ın top-k değerini değiştirmez.
FALLBACK_COMPOSER_TOP_K = 4


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
            "version": result[
                "metadata"
            ].get(
                "version",
                "Bilinmiyor",
            ),
            "clause": result[
                "metadata"
            ].get(
                "clause",
                "Bilinmiyor",
            ),
            "clause_title": result[
                "metadata"
            ].get(
                "clause_title",
                "",
            ),
            "status": result[
                "metadata"
            ].get(
                "status",
                "Bilinmiyor",
            ),
            "source_url": result[
                "metadata"
            ].get(
                "source_url",
                "",
            ),
            "distance": result.get(
                "distance",
                0.0,
            ),
        }
        for result in results
    ]


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
    # EXPLICIT RFC QUESTIONS
    # -----------------------------------------------------
    #
    # Bir protokolün hangi RFC'de tanımlandığını soran
    # sorgularda secondary RFC'ler semantic olarak ana
    # RFC'den daha yüksek gelebiliyor.
    #
    # Bu nedenle yalnızca explicit RFC sorularında
    # answer-free teknik query'lerle ikinci pass yapılır.
    # -----------------------------------------------------

    if (
        answer_type
        == "STANDART / DOKÜMAN"
        and re.search(
            r"\brfc\b",
            question or "",
            flags=re.IGNORECASE,
        )
    ):
        return True

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
        answer_type
        in {
            "STANDART / DOKÜMAN",
            "DEĞER / LİMİT",
        }
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

def _extract_fallback_anchors(
    question: str,
) -> list[str]:
    """
    Sorudaki güçlü teknik identifier / acronym'leri çıkarır.

    Örnek:
        E.164
        G.711
        H.248
        HTTP/3
        QUIC
        5QI

    Bu liste cevap içermez.
    Yalnızca kullanıcının yazdığı teknik anchor'ları kullanır.
    """

    text = (
        question
        or ""
    ).strip()

    anchors: list[str] = []

    patterns = [
        # ITU tarzı identifier:
        # E.164, G.711, H.248
        r"\b[A-Za-z]\.\d+(?:\.\d+)*\b",

        # HTTP/3 gibi slash identifier
        r"\b[A-Za-z][A-Za-z0-9\-]*/\d+\b",

        # 5QI vb.
        r"\b\d[A-Z]{2,8}\b",
    ]

    for pattern in patterns:
        for match in re.findall(
            pattern,
            text,
            flags=re.IGNORECASE,
        ):
            clean = (
                match
                or ""
            ).strip()

            if (
                clean
                and clean.casefold()
                not in {
                    item.casefold()
                    for item in anchors
                }
            ):
                anchors.append(
                    clean
                )

    # RFC sorularında QUIC gibi teknik acronym de
    # güçlü anchor olarak kullanılabilir.
    if re.search(
        r"\brfc\b",
        text,
        flags=re.IGNORECASE,
    ):
        acronyms = re.findall(
            r"\b[A-Z][A-Z0-9\-]{2,12}\b",
            text,
        )

        for acronym in acronyms:
            if acronym in {
                "RFC",
                "IETF",
                "TS",
                "TR",
            }:
                continue

            if (
                acronym.casefold()
                not in {
                    item.casefold()
                    for item in anchors
                }
            ):
                anchors.append(
                    acronym
                )

    return anchors


def _exact_anchor_candidates(
    question: str,
) -> list[dict[str, Any]]:
    """
    Teknik identifier geçen chunk'ları doğrudan DB'den toplar.

    Semantic similarity kullanılmaz.

    Amaç:
        E.164 gibi güçlü teknik identifier'ların
        "number", "length" gibi genel kelimeler tarafından
        bastırılmasını önlemek.
    """

    anchors = (
        _extract_fallback_anchors(
            question
        )
    )

    if not anchors:
        return []

    print(
        "[FALLBACK] Exact anchor:",
        anchors,
    )

    candidates: list[
        dict[str, Any]
    ] = []

    seen: set[
        tuple[str, str, str, str]
    ] = set()

    for anchor in anchors:
        result = (
            retriever.collection.get(
                where_document={
                    "$contains": anchor
                },
                limit=200,
                include=[
                    "documents",
                    "metadatas",
                ],
            )
        )

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

            key = (
                str(
                    clean_metadata.get(
                        "org",
                        "",
                    )
                ),
                str(
                    clean_metadata.get(
                        "code",
                        "",
                    )
                ),
                str(
                    clean_metadata.get(
                        "clause",
                        "",
                    )
                ),
                clean_text,
            )

            if key in seen:
                continue

            seen.add(
                key
            )

            candidates.append(
                {
                    "chunk_id": (
                        chunk_id
                    ),
                    "text": (
                        clean_text
                    ),
                    "metadata": (
                        clean_metadata
                    ),

                    # collection.get distance üretmez.
                    # Reranker için buna ihtiyaç yok.
                    "distance": 0.0,
                }
            )

    print(
        "[FALLBACK] Exact-anchor aday:",
        len(candidates),
    )

    return candidates

def _exact_phrase_candidates(
    question: str,
) -> list[dict[str, Any]]:
    """
    Teknik query varyantlarını önce hızlı semantic
    aramayla küçük bir aday havuzuna indirir.

    Ardından yalnızca bu küçük havuzda exact phrase
    kontrolü yapılır.

    Böylece 410K+ chunk üzerinde where_document
    full scan yapılmaz.
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
        else []
    )

    if not phrase_queries:
        return []

    print(
        "[FALLBACK] Exact phrase sorguları:",
        phrase_queries,
    )

    # -----------------------------------------------------
    # 1. PHRASE'LERİ TEK BATCH'TE EMBED ET
    # -----------------------------------------------------

    embeddings = (
        retriever
        .embedding_service
        .embed_queries(
            phrase_queries
        )
    )

    # -----------------------------------------------------
    # 2. SADECE KÜÇÜK SEMANTIC ADAY HAVUZU
    # -----------------------------------------------------
    #
    # 410K dokümanı text scan etmek yerine,
    # her phrase için en yakın 60 chunk alınır.
    # -----------------------------------------------------

    result = (
        retriever.collection.query(
            query_embeddings=embeddings,
            n_results=60,
            include=[
                "documents",
                "metadatas",
                "distances",
            ],
        )
    )

    all_ids = result.get(
        "ids",
        [],
    )

    all_documents = result.get(
        "documents",
        [],
    )

    all_metadatas = result.get(
        "metadatas",
        [],
    )

    all_distances = result.get(
        "distances",
        [],
    )

    candidates: dict[
        tuple[str, str, str, str],
        dict[str, Any],
    ] = {}

    # -----------------------------------------------------
    # 3. SADECE BU 60'LAR İÇİNDE EXACT PHRASE KONTROLÜ
    # -----------------------------------------------------

    for query_index, phrase in enumerate(
        phrase_queries
    ):
        if query_index >= len(all_ids):
            continue

        phrase_normalized = (
            phrase
            .casefold()
            .strip()
        )

        ids = all_ids[
            query_index
        ]

        documents = all_documents[
            query_index
        ]

        metadatas = all_metadatas[
            query_index
        ]

        distances = all_distances[
            query_index
        ]

        phrase_hit_count = 0

        for (
            chunk_id,
            document,
            metadata,
            distance,
        ) in zip(
            ids,
            documents,
            metadatas,
            distances,
        ):
            text = (
                document
                or ""
            ).strip()

            clean_metadata = (
                metadata
                or {}
            )

            if not text:
                continue

            if clean_metadata.get(
                "status"
            ) not in {
                "available",
                "indexed",
            }:
                continue

            # Exact phrase yalnızca küçük semantic
            # aday havuzunda kontrol edilir.
            if (
                phrase_normalized
                not in text.casefold()
            ):
                continue

            phrase_hit_count += 1

            key = (
                str(
                    clean_metadata.get(
                        "org",
                        "",
                    )
                ),
                str(
                    clean_metadata.get(
                        "code",
                        "",
                    )
                ),
                str(
                    clean_metadata.get(
                        "clause",
                        "",
                    )
                ),
                text,
            )

            distance_value = (
                float(distance)
                if distance is not None
                else 1.0
            )

            existing = (
                candidates.get(
                    key
                )
            )

            if existing is None:
                candidates[
                    key
                ] = {
                    "chunk_id": chunk_id,
                    "text": text,
                    "metadata": (
                        clean_metadata
                    ),
                    "distance": (
                        distance_value
                    ),
                    "exact_phrase_hits": 1,
                }

            else:
                existing[
                    "exact_phrase_hits"
                ] += 1

                if (
                    distance_value
                    < existing[
                        "distance"
                    ]
                ):
                    existing[
                        "distance"
                    ] = (
                        distance_value
                    )

        print(
            f"[FALLBACK] Phrase hit "
            f"'{phrase}': "
            f"{phrase_hit_count}"
        )

    ranked = sorted(
        candidates.values(),
        key=lambda item: (
            -item[
                "exact_phrase_hits"
            ],
            item[
                "distance"
            ],
        ),
    )

    print(
        "[FALLBACK] Exact phrase toplam aday:",
        len(ranked),
    )

    return ranked

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
        :FALLBACK_RERANK_TOP_K
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

        print(
            "[FALLBACK] Composer evidence chunk:",
            len(
                fallback_prompt_results
            ),
        )

        if fallback_prompt_results:
            fallback_composer_start = (
                time.perf_counter()
            )

            (
                fallback_composition,
                fallback_rendered,
            ) = _compose_and_render(
                question=message,
                chunks=(
                    fallback_prompt_results
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

                return {
                    "reply": reply,
                    "sources": (
                        _build_sources(
                            fallback_prompt_results
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