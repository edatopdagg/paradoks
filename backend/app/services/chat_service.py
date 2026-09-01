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
    build_system_prompt,
    build_user_prompt,
    infer_answer_type,
)
from app.services.question_analysis import (
    allows_deterministic_fast_path,
    build_chroma_where,
    build_result_deduplication_key,
    extract_document_constraint,
    has_usable_evidence,
    is_multi_part_question,
    is_low_value_clause,
    result_matches_document_constraint,
)

from app.services.lexical_search_service import (
    LexicalSearchService,
)
from app.services.retriever import Retriever
from app.services.reranker_service import Reranker


# =========================================================
# PIPELINE AYARLARI
# =========================================================

RETRIEVAL_TOP_K = 12
PROMPT_TOP_K = 3
STRONG_RERANK_SCORE = 7.0
STRONG_RERANK_MARGIN = 2.0

# =========================================================
# CONTROLLED FALLBACK AYARLARI
# =========================================================

FALLBACK_COMPOSER_TOP_K = 4
DOCUMENT_FALLBACK_COMPOSER_TOP_K = 20

# =========================================================
# DETERMINISTIC FAST-PATH TYPES
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
    unique_results: list[dict[str, Any]] = []
    seen: set[tuple[str, ...]] = set()

    for result in results:
        key = build_result_deduplication_key(result)
        if key in seen:
            continue
        seen.add(key)
        unique_results.append(result)

    return unique_results


def _filter_available_results(
    results: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    return [
        result
        for result in results
        if result.get("metadata", {}).get("status") in {"available", "indexed"}
    ]


def _filter_blocked_results(
    results: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    return [
        result
        for result in results
        if result.get("metadata", {}).get("status") == "blocked"
    ]


def _prefer_content_results(
    question: str,
    results: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if _is_document_question(question):
        return results

    content_results = [
        result
        for result in results
        if not is_low_value_clause(
            str(result.get("metadata", {}).get("clause", "")),
            str(result.get("metadata", {}).get("clause_title", "")),
        )
    ]

    return content_results or results


def _select_prompt_results(
    question: str,
    results: list[dict[str, Any]],
    limit: int = PROMPT_TOP_K,
) -> list[dict[str, Any]]:
    selected = results[:limit]

    if len(selected) < 2 or is_multi_part_question(question):
        return selected

    top_score = float(selected[0].get("rerank_score", 0.0))
    second_score = float(selected[1].get("rerank_score", 0.0))

    if top_score >= STRONG_RERANK_SCORE and (top_score - second_score) >= STRONG_RERANK_MARGIN:
        print(
            "[EVIDENCE] Güçlü skor farkı; tek chunk kullanılacak:",
            f"{top_score:.4f} vs {second_score:.4f}",
        )
        return selected[:1]

    return selected


# =========================================================
# SOURCE BUILDERS
# =========================================================

def _build_blocked_sources(
    blocked_results: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    return [
        {
            "org": result["metadata"].get("org", "Bilinmiyor"),
            "code": result["metadata"].get("code", "Bilinmiyor"),
            "source_url": result["metadata"].get("source_url", ""),
        }
        for result in blocked_results
    ]


def _build_sources(
    results: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    sources: list[dict[str, Any]] = []
    seen: set[tuple[str, ...]] = set()

    for result in results:
        metadata = result.get("metadata", {})
        org = str(metadata.get("org", "Bilinmiyor") or "Bilinmiyor")
        code = str(metadata.get("code", "Bilinmiyor") or "Bilinmiyor")
        version = str(metadata.get("version", "Bilinmiyor") or "Bilinmiyor")

        if re.search(r"https?://", version, flags=re.IGNORECASE):
            version = "Bilinmiyor"

        clause = str(metadata.get("clause", "Bilinmiyor") or "Bilinmiyor")
        source_url = str(metadata.get("source_url", "") or "")

        page_start_value = metadata.get("page_start")
        page_end_value = metadata.get("page_end")

        page_start = (
            page_start_value
            if isinstance(page_start_value, int)
            and page_start_value >= 0
            else None
        )

        page_end = (
            page_end_value
            if isinstance(page_end_value, int)
            and page_end_value >= 0
            else None
        )

        if source_url:
            key = ("url", source_url.casefold(), clause.casefold())
        else:
            key = ("metadata", org.casefold(), code.casefold(), version.casefold(), clause.casefold())

        if key in seen:
            continue

        seen.add(key)
        sources.append(
            {
                "org": org,
                "code": code,
                "version": version,
                "clause": clause,
                "clause_title": metadata.get("clause_title", ""),
                "status": metadata.get("status", "Bilinmiyor"),
                "source_url": source_url,
                "distance": result.get("distance", 0.0),

                "source_id": str(
                    metadata.get("source_id", "")
                    or result.get("id", "")
                    or ""
                ),
                "document_id": str(
                    metadata.get("document_id", "")
                    or ""
                ),
                "version_id": str(
                    metadata.get("version_id", "")
                    or ""
                ),
                "clause_id": str(
                    metadata.get("clause_id", "")
                    or ""
                ),

                "page_number": page_start,
                "page_start": page_start,
                "page_end": page_end,

                "viewer_url": str(
                    metadata.get("viewer_url", "")
                    or ""
                ),
                "local_path": str(
                    metadata.get("local_path", "")
                    or ""
                ),
                "highlight_text": str(
                    result.get("text", "")
                    or ""
                ),

                "char_start": metadata.get(
                    "char_start"
                ),
                "char_end": metadata.get(
                    "char_end"
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
) -> tuple[dict[str, Any], dict[str, Any]]:
    composition = compose_answer_evidence(question=question, chunks=chunks)
    rendered = render_composed_answer(question=question, composition=composition)
    return composition, rendered


def _can_use_fast_path(
    question: str,
    composition: dict[str, Any],
    rendered: dict[str, Any],
) -> bool:
    answer_type = str(composition.get("answer_type", ""))
    confidence = str(composition.get("confidence", "low"))
    renderer_success = bool(rendered.get("success", False))
    reply = str(rendered.get("reply", "") or "").strip()

    # Eğer standart/doküman veya referans noktası gibi yüksek güvenli bir tespit varsa doğrudan izin ver

    return (
        answer_type in FAST_PATH_TYPES
        and allows_deterministic_fast_path(question, answer_type)
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
    answer_numbers = re.findall(r"\d+(?:\.\d+)?", primary_answer or "")
    if not answer_numbers:
        return False

    normalized_question = (question or "").casefold()
    return any(number in normalized_question for number in answer_numbers)


def _precision_fallback_phrases(
    question: str,
) -> list[str]:
    normalized_question = (question or "").casefold()

    service_request_intent = "service request" in normalized_question or (
        "uplink" in normalized_question
        and any(
            val in normalized_question
            for val in (
                "yeniden etkinleştir",
                "tekrar etkinleştir",
                "tekrar aktif",
                "activate",
                "reactivate",
            )
        )
    )

    if service_request_intent:
        return ["Service Request procedure is used"]

    http3_intent = "http/3" in normalized_question or "http3" in normalized_question
    specialized_http3_subject = any(val in normalized_question for val in ("websocket", "qpack"))

    if (
        http3_intent
        and not specialized_http3_subject
        and any(
            val in normalized_question
            for val in ("rfc", "standart", "standard", "doküman", "document", "tanımlan", "defined")
        )
    ):
        return ["This document defines HTTP/3"]

    if "quic" in normalized_question and any(
        val in normalized_question for val in ("kayıp", "loss", "congestion", "recovery")
    ):
        return ["This document describes loss detection and congestion control mechanisms for QUIC"]

    cell_broadcast_intent = any(
        val in normalized_question for val in ("cell broadcast", "warning message", "uyarı mesaj")
    )
    cancellation_intent = any(val in normalized_question for val in ("iptal", "cancel", "stop", "durdur"))

    if cell_broadcast_intent and cancellation_intent:
        return ["The cancel warning message delivery procedure takes place"]

    if "5g" in normalized_question and any(val in normalized_question for val in ("mimarisi", "architecture", "sistem mimarisi")):
        if any(val in normalized_question for val in ("şartname", "sartname", "standart", "standard", "doküman", "document")):
            return ["System Architecture for the 5G System", "3GPP TS 23.501"]

    return []


def _is_reference_point_question(
    question: str,
) -> bool:
    val = (question or "").casefold()
    return "referans nokta" in val or "reference point" in val


def _reference_point_fts_queries(
    question: str,
) -> list[str]:
    explicit_reference_point = re.search(
        r"\b(N\d{1,3})\b",
        question or "",
        flags=re.IGNORECASE,
    )

    if explicit_reference_point:
        reference_point = (
            explicit_reference_point
            .group(1)
            .upper()
        )

        upper_question = (
            question
            or ""
        ).upper()

        technical_tokens = [
            token
            for token in (
                "NAS",
                "UE",
                "AMF",
                "SMF",
                "UPF",
                "AUSF",
                "UDM",
                "PCF",
                "NSSF",
                "NRF",
            )
            if re.search(
                rf"\b{re.escape(token)}\b",
                upper_question,
            )
        ]

        if (
            reference_point == "N1"
            and "NAS" not in technical_tokens
        ):
            technical_tokens.insert(
                0,
                "NAS",
            )

        query_terms = [
            reference_point,
            *technical_tokens,
        ]

        if len(query_terms) == 1:
            query_terms.append(
                "reference point"
            )

        return [
            " AND ".join(
                f'"{term}"'
                for term in query_terms
            )
        ]

    stop_tokens = {
        "5G", "5GS", "TS", "TR", "RFC", "REFERENCE", "POINT", "INTERFACE", 
        "HTTP", "IETF", "ILE", "ARASINDAKI", "ARASINDA", "HANGISIDIR", 
        "NEDIR", "HANGI", "BETWEEN", "AND", "THE"
    }

    raw_tokens = re.findall(r"\b(?:NG-RAN|gNB|gNodeB|eNB|[A-Za-z0-9/\-]{2,})\b", question or "")
    
    normalized_endpoints: list[str] = []
    for token in raw_tokens:
        clean = token.upper()
        if clean in stop_tokens:
            continue
        if clean in {"GNB", "GNODEB", "ENB", "NG-RAN", "(R)AN"}:
            clean = "RAN"
        if clean not in normalized_endpoints:
            normalized_endpoints.append(clean)

    if len(normalized_endpoints) < 2:
        return []

    first, second = normalized_endpoints[0], normalized_endpoints[1]

    queries = []
    # RAN ile ilgili ise 3GPP'nin yaygın "(R)AN", "NG-RAN" ve "TS 23.501" biçimlerini ekle
    if "RAN" in (first, second):
        other = second if first == "RAN" else first
        queries.extend([
            f'"Reference point between" AND "{other}"',
            f'"Reference points" AND "{other}"',
            f'"(R)AN" AND "{other}"',
            f'"NG-RAN" AND "{other}"',
            f'"N2" AND "{other}"',
        ])
    else:
        queries.extend([
            f'"reference point between" AND "{first}" AND "{second}"',
            f'"reference point" AND "{first}" AND "{second}"',
            f'"{first}" AND "{second}" AND "reference point"',
        ])

    return queries


def _is_document_question(
    question: str,
) -> bool:
    return infer_answer_type(question) == "STANDART / DOKÜMAN"


def _needs_targeted_fallback(
    question: str,
    composition: dict[str, Any],
    rendered: dict[str, Any],
) -> bool:
    answer_type = str(composition.get("answer_type", ""))
    confidence = str(composition.get("confidence", "low"))
    primary_answer = str(composition.get("primary_answer", "") or "").strip()
    renderer_success = bool(rendered.get("success", False))

    # Eğer standart/doküman sorusunda ilk aşamada zaten yüksek güvenle bir doküman bulunduysa fallback yapma
    if _is_document_question(question) and confidence == "high" and primary_answer and renderer_success:
        return False

    if _is_reference_point_question(question):
        return True

    # Genel NF (Ağ Fonksiyonları) mimari sorularında fallback kontrolü
    if any(
        re.search(r"\b" + nf + r"\b", question, flags=re.IGNORECASE)
        for nf in ["amf", "smf", "upf", "ausf", "udm", "pcf", "nssf", "nrf"]
    ):
        return True

    precision_phrases = _precision_fallback_phrases(question)
    if precision_phrases:
        return True

    if _is_document_question(question):
        return True

    if answer_type == "DEĞER / LİMİT" and primary_answer and _value_answer_echoes_question(
        question=question,
        primary_answer=primary_answer,
    ):
        return True

    if answer_type == "DEĞER / LİMİT" and (confidence != "high" or not renderer_success):
        return True

    return False

# =========================================================
# TARGETED SECOND-PASS RETRIEVAL
# =========================================================

def _document_fallback_candidates(
    question: str,
) -> list[dict[str, Any]]:
    search_queries = retriever.query_normalizer.normalize(question, max_variants=4)
    phrase_queries = search_queries[1:] if len(search_queries) > 1 else search_queries

    precision_phrases = _precision_fallback_phrases(question)
    if precision_phrases:
        phrase_queries = precision_phrases + phrase_queries

    print("[FALLBACK] Document discovery sorguları:", phrase_queries)

    candidates: list[dict[str, Any]] = []
    seen_chunk_ids: set[str] = set()

    for phrase in phrase_queries:
        words = [w for w in re.findall(r"[A-Za-z0-9/]+", phrase) if len(w) > 1]
        if not words:
            continue
        
        # 'this', 'document', 'defines' gibi generic kelimeleri temizleyip teknik kelimeleri FTS5'e zorunlu yap
        clean_words = [w for w in words if w.casefold() not in {"this", "the", "document", "defines", "specifies", "protocol", "overview"}]
        
        if clean_words:
            # Örneğin: "HTTP" AND "3" AND "RFC"
            flexible_query = " AND ".join(f'"{w}"' for w in clean_words)
        else:
            flexible_query = " AND ".join(f'"{w}"' for w in words[:4])
        
        results = lexical_search.search_query(query=flexible_query, limit=15)
        print(f"[FALLBACK] Document hit '{flexible_query}': {len(results)}")

        for result in results:
            chunk_id = str(result.get("chunk_id", ""))
            if chunk_id and chunk_id in seen_chunk_ids:
                continue
            if chunk_id:
                seen_chunk_ids.add(chunk_id)
            candidates.append(result)

    print("[FALLBACK] Document toplam unique aday:", len(candidates))
    return candidates[:DOCUMENT_FALLBACK_COMPOSER_TOP_K]

def _parse_primary_document_identity(
    primary_answer: str,
) -> tuple[str, str] | None:
    answer = (primary_answer or "").strip()
    if not answer:
        return None

    rfc_match = re.fullmatch(r"RFC\s+(\d+)", answer, flags=re.IGNORECASE)
    if rfc_match:
        return ("IETF", rfc_match.group(1))

    spec_match = re.fullmatch(r"(3GPP|ETSI)\s+(TS|TR)\s+([\d.]+)", answer, flags=re.IGNORECASE)
    if spec_match:
        return (spec_match.group(1).upper(), f"{spec_match.group(2).upper()} {spec_match.group(3)}")

    return None


def _document_source_quality_score(
    result: dict[str, Any],
) -> float:
    metadata = result.get("metadata", {})
    clause_title = str(metadata.get("clause_title", "") or "").casefold()
    text = str(result.get("text", "") or "").casefold()

    score = 0.0
    if "scope" in clause_title:
        score += 10.0
    if any(val in clause_title for val in ("introduction", "overview")):
        score += 7.0
    if "reference" in clause_title:
        score -= 10.0
    if re.search(r"\b(?:this document|the present document)\s+(?:defines|specifies|describes)\b", text, flags=re.IGNORECASE):
        score += 10.0

    return score


def _fetch_primary_document_sources(
    question: str,
    primary_answer: str,
    limit: int = 4,
) -> list[dict[str, Any]]:
    identity = _parse_primary_document_identity(primary_answer)
    if identity is None:
        return []

    org, code = identity

    try:
        result = retriever.collection.get(
            where={"code": code},
            limit=40,
            include=["documents", "metadatas"],
        )
    except Exception as error:
        print("[SOURCE] Primary document lookup failed:", error)
        return []

    candidates: list[dict[str, Any]] = []
    for chunk_id, document, metadata in zip(
        result.get("ids", []),
        result.get("documents", []),
        result.get("metadatas", []),
    ):
        clean_text = (document or "").strip()
        clean_metadata = metadata or {}

        if not clean_text or clean_metadata.get("status") not in {"available", "indexed"}:
            continue

        if clean_metadata.get("org", "").upper() != org.upper():
            continue

        candidates.append({
            "chunk_id": chunk_id,
            "text": clean_text,
            "metadata": clean_metadata,
            "distance": 0.0,
        })

    candidates = _deduplicate_results(candidates)
    if not candidates:
        return []

    quality_candidates = [c for c in candidates if _document_source_quality_score(c) > 0.0]
    rerank_pool = quality_candidates if quality_candidates else candidates

    if len(rerank_pool) == 1:
        return rerank_pool[:limit]

    try:
        ranked = reranker.rerank(
            query=question,
            candidates=rerank_pool,
            top_k=min(limit, len(rerank_pool)),
        )
        if ranked:
            return sorted(ranked, key=_document_source_quality_score, reverse=True)[:limit]
    except Exception as error:
        print("[SOURCE] Primary document rerank failed:", error)

    return sorted(rerank_pool, key=_document_source_quality_score, reverse=True)[:limit]


def _select_document_source_results(
    results: list[dict[str, Any]],
    primary_answer: str,
    question: str = "",
    limit: int = 4,
) -> list[dict[str, Any]]:
    answer = (primary_answer or "").strip()
    if not answer:
        return results[:limit]

    identity = _parse_primary_document_identity(answer)
    direct_matches: list[dict[str, Any]] = []

    if identity is not None:
        expected_org, expected_code = identity
        for result in results:
            metadata = result.get("metadata", {})
            org = str(metadata.get("org", "") or "").strip()
            code = str(metadata.get("code", "") or "").strip()

            if org.casefold() == expected_org.casefold() and code.casefold() == expected_code.casefold():
                direct_matches.append(result)

    if question:
        hydrated_matches = _fetch_primary_document_sources(
            question=question,
            primary_answer=answer,
            limit=limit,
        )
        if hydrated_matches:
            print("[SOURCE] Primary document hydrated:", answer, "| chunk:", len(hydrated_matches))
            return hydrated_matches

    if direct_matches:
        return _deduplicate_results(direct_matches)[:limit]

    answer_tokens = [answer]
    rfc_match = re.fullmatch(r"RFC\s+(\d+)", answer, flags=re.IGNORECASE)
    if rfc_match:
        answer_tokens.append(f"RFC{rfc_match.group(1)}")

    referenced_matches = [
        result
        for result in results
        if any(token.casefold() in str(result.get("text", "") or "").casefold() for token in answer_tokens)
    ]

    if referenced_matches:
        return referenced_matches[:limit]

    return results[:limit]


def _targeted_fallback_retrieval(
    question: str,
) -> list[dict[str, Any]]:
    # 1. Yalnızca gerçek referans noktası sorularında reference point FTS yap
    if _is_reference_point_question(question):
        reference_queries = _reference_point_fts_queries(question)
        technical_variants = retriever.query_normalizer.normalize(question, max_variants=4)[1:]

        for reference_query in reference_queries:
            print("[FALLBACK] Reference-point FTS:", reference_query)
            reference_results = lexical_search.search_query(query=reference_query, limit=20)

            if not reference_results:
                continue

            reference_results = _prefer_content_results(
                question,
                _deduplicate_results(reference_results),
            )

            constraint = extract_document_constraint(question)
            if constraint:
                reference_results = [
                    result
                    for result in reference_results
                    if result_matches_document_constraint(result, constraint)
                ]

            if not reference_results:
                continue

            enriched_reference_results: list[dict[str, Any]] = []
            for result in reference_results:
                enriched = dict(result)
                matched_queries = list(enriched.get("matched_queries", []))
                for variant in technical_variants:
                    if variant not in matched_queries:
                        matched_queries.append(variant)
                enriched["matched_queries"] = matched_queries
                enriched_reference_results.append(enriched)

            reference_results = enriched_reference_results
            print("[FALLBACK] Reference-point aday:", len(reference_results))

            try:
                ranked_reference_results = reranker.rerank(
                    query=question,
                    candidates=reference_results,
                    top_k=min(FALLBACK_COMPOSER_TOP_K, len(reference_results)),
                )

                for index, result in enumerate(ranked_reference_results, start=1):
                    metadata = result.get("metadata", {})
                    print(
                        f"[FALLBACK RERANK] {index}. "
                        f"{metadata.get('org', 'Bilinmiyor')} "
                        f"{metadata.get('code', 'Bilinmiyor')} | "
                        f"Madde {metadata.get('clause', 'Bilinmiyor')} | "
                        f"Skor: {float(result.get('rerank_score', 0.0)):.4f}"
                    )

                return ranked_reference_results
            except Exception as error:
                print("[FALLBACK] Reference-point rerank failed:", error)
                return reference_results[:FALLBACK_COMPOSER_TOP_K]

    # 2. Doküman sorusuysa doğrudan doküman fallback'ine git
    if _is_document_question(question):
        return _document_fallback_candidates(question)

    # 3. Precision fallback veya normal teknik varyantlar
    precision_phrases = _precision_fallback_phrases(question)
    search_queries = retriever.query_normalizer.normalize(question, max_variants=4)
    technical_variants = search_queries[1:] if len(search_queries) > 1 else []
    
    phrase_queries = precision_phrases if precision_phrases else technical_variants

    if not phrase_queries:
        return []

    print("[FALLBACK] FTS5 phrase sorguları:", phrase_queries)

    candidates: list[dict[str, Any]] = []
    seen_chunk_ids: set[str] = set()

    for phrase in phrase_queries:
        words = [w for w in re.findall(r"[A-Za-z0-9]+", phrase) if len(w) > 2]
        if not words:
            continue
        flexible_query = " AND ".join(f'"{w}"' for w in words[:3])

        results = lexical_search.search_query(
            query=flexible_query,
            limit=20,
        )

        print(f"[FALLBACK] FTS5 hit '{flexible_query}': {len(results)}")

        for result in results:
            chunk_id = str(result.get("chunk_id", ""))
            if chunk_id and chunk_id in seen_chunk_ids:
                continue
            if chunk_id:
                seen_chunk_ids.add(chunk_id)
            candidates.append(result)

    candidates = _prefer_content_results(
        question,
        _deduplicate_results(candidates),
    )

    constraint = extract_document_constraint(question)
    if constraint:
        candidates = [
            result
            for result in candidates
            if result_matches_document_constraint(result, constraint)
        ]

    candidates = _deduplicate_results(candidates)
    print("[FALLBACK] FTS5 toplam unique aday:", len(candidates))

    if not candidates:
        return []

    try:
        rerank_query = technical_variants[0] if technical_variants else question

        enriched_candidates = []
        for candidate in candidates:
            enriched = dict(candidate)
            matched = list(enriched.get("matched_queries", []))
            for v in technical_variants:
                if v not in matched:
                    matched.append(v)
            enriched["matched_queries"] = matched
            enriched_candidates.append(enriched)

        ranked_candidates = reranker.rerank(
            query=rerank_query,
            candidates=enriched_candidates,
            top_k=FALLBACK_COMPOSER_TOP_K,
        )
        for idx, res in enumerate(ranked_candidates, start=1):
            meta = res.get("metadata", {})
            print(f"[FALLBACK RERANK] {idx}. {meta.get('code')} | Madde {meta.get('clause')} | Skor: {float(res.get('rerank_score', 0.0)):.4f}")
        return ranked_candidates
    except Exception as err:
        print("[FALLBACK] Rerank hatası:", err)
        return candidates[:FALLBACK_COMPOSER_TOP_K]


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
    print("=" * 50)
    print("[PERF] Paradoks Pipeline")
    print(f"[PERF] Retrieval: {retrieval_time:.2f} sn")
    print(f"[PERF] Reranker: {reranker_time:.2f} sn")
    print(f"[PERF] Composer + Renderer: {composer_time:.4f} sn")
    print(f"[PERF] Targeted fallback: {fallback_time:.2f} sn")
    print(f"[PERF] Prompt: {prompt_time:.4f} sn")
    print(f"[PERF] Ollama: {ollama_time:.2f} sn")
    print(f"[PERF] Answer Guard CPU: {guard_time:.4f} sn")
    print("[PERF] Deterministic cevap:", "EVET" if deterministic_used else "HAYIR")
    print("[PERF] Guard repair:", "EVET" if repair_used else "HAYIR")
    print(f"[PERF] Total: {total_time:.2f} sn")
    print("=" * 50)
    print()


def _fallback_scores_are_usable(
    results: list[dict[str, Any]],
) -> bool:
    if not results:
        return False

    scores: list[float] = []
    for result in results:
        if "rerank_score" not in result:
            continue
        try:
            scores.append(float(result["rerank_score"]))
        except (TypeError, ValueError):
            continue

    if not scores:
        return True

    return max(scores) >= 0.0


def _best_rerank_score(
    results: list[dict[str, Any]],
) -> float | None:
    scores: list[float] = []
    for result in results:
        if "rerank_score" not in result:
            continue
        try:
            scores.append(float(result["rerank_score"]))
        except (TypeError, ValueError):
            continue

    return max(scores) if scores else None


def _fallback_outperforms_normal_evidence(
    fallback_results: list[dict[str, Any]],
    normal_results: list[dict[str, Any]],
    question: str = "",
) -> bool:
    if not fallback_results:
        return False
    if not normal_results:
        return True

    # 1. Normal evidence bir Teknik Rapor (TR) ise ve fallback'te TS standardı varsa fallback üstündür
    normal_code = str(normal_results[0].get("metadata", {}).get("code", "")).upper()
    fallback_code = str(fallback_results[0].get("metadata", {}).get("code", "")).upper()
    
    if "TR " in normal_code and "TS " in fallback_code:
        print(f"[EVIDENCE GATE] Normal evidence TR ({normal_code}) olduğu için TS fallback ({fallback_code}) tercih edildi.")
        return True

    # 2. Ağ fonksiyonu uyumsuzluğu kontrolü
    nf_match = re.search(r"\b(AMF|SMF|UPF|AUSF|UDM|PCF|NSSF|NRF)\b", question or "", flags=re.IGNORECASE)
    if nf_match:
        target_nf = nf_match.group(1).upper()
        normal_first_title = str(normal_results[0].get("metadata", {}).get("clause_title", "")).upper()
        
        if target_nf not in normal_first_title and any(other in normal_first_title for other in ["AMF", "SMF", "UPF"] if other != target_nf):
            print(f"[EVIDENCE GATE] Entity uyuşmazlığı tespit edildi, fallback tercih ediliyor.")
            return True

    fallback_score = _best_rerank_score(fallback_results)
    normal_score = _best_rerank_score(normal_results)

    if fallback_score is None or normal_score is None:
        return True

    return fallback_score >= normal_score

# =========================================================
# MAIN PIPELINE
# =========================================================

def generate_reply(
    message: str,
) -> dict[str, Any]:
    total_start = time.perf_counter()

    reranker_time = 0.0
    composer_time = 0.0
    fallback_time = 0.0
    prompt_time = 0.0
    ollama_time = 0.0
    guard_time = 0.0

    repair_used = False
    deterministic_used = False

    document_constraint = extract_document_constraint(message)
    retrieval_where = build_chroma_where(document_constraint)

    if document_constraint:
        print("[PIPELINE] Açık doküman filtresi:", document_constraint)

    retrieval_start = time.perf_counter()
    results = retriever.search(
        query=message,
        top_k=RETRIEVAL_TOP_K,
        where=retrieval_where,
    )
    retrieval_time = time.perf_counter() - retrieval_start

    available_results = _filter_available_results(results)
    blocked_results = _filter_blocked_results(results)
    available_results = _deduplicate_results(available_results)

    if document_constraint:
        available_results = [
            result
            for result in available_results
            if result_matches_document_constraint(result, document_constraint)
        ]

    available_results = _prefer_content_results(message, available_results)

    print("[PIPELINE] Retrieval aday:", len(results))
    print("[PIPELINE] Kullanılabilir unique aday:", len(available_results))

    if not available_results:
        total_time = time.perf_counter() - total_start
        _print_performance(
            retrieval_time=retrieval_time,
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
            "reply": "Bu soruyu yanıtlamak için erişilebilir bir standart maddesi bulunamadı.",
            "sources": [],
            "blocked_sources": _build_blocked_sources(blocked_results),
        }

    # Bütün available adayları CrossEncoder'a veriyoruz (kesilme olmasın)
    reranker_start = time.perf_counter()
    if len(available_results) == 1:
        reranked_results = available_results
    else:
        reranked_results = reranker.rerank(
            query=message,
            candidates=available_results,
            top_k=len(available_results),
        )
    reranker_time = time.perf_counter() - reranker_start

    prompt_results = _select_prompt_results(message, reranked_results)
    print("[PIPELINE] Normal evidence chunk:", len(prompt_results))

    for index, result in enumerate(prompt_results, start=1):
        metadata = result.get("metadata", {})
        print(
            f"[RERANK] {index}. "
            f"{metadata.get('org', 'Bilinmiyor')} "
            f"{metadata.get('code', 'Bilinmiyor')} | "
            f"Madde {metadata.get('clause', 'Bilinmiyor')} | "
            f"Başlık: {metadata.get('clause_title', '')} | "
            f"Skor: {float(result.get('rerank_score', 0.0)):.4f}"
        )

    composer_start = time.perf_counter()
    composition, rendered = _compose_and_render(question=message, chunks=reranked_results[:DOCUMENT_FALLBACK_COMPOSER_TOP_K])
    composer_time += time.perf_counter() - composer_start

    print("[COMPOSER] Answer type:", composition.get("answer_type"))
    print("[COMPOSER] Primary:", composition.get("primary_answer"))
    print("[COMPOSER] Confidence:", composition.get("confidence"))

    fallback_required = _needs_targeted_fallback(
        question=message,
        composition=composition,
        rendered=rendered,
    )

    if not fallback_required and _can_use_fast_path(
        message,
        composition,
        rendered,
    ):
        deterministic_used = True
        reply = str(rendered.get("reply", ""))
        total_time = time.perf_counter() - total_start
        _print_performance(
            retrieval_time=retrieval_time,
            reranker_time=reranker_time,
            composer_time=composer_time,
            fallback_time=0.0,
            prompt_time=0.0,
            ollama_time=0.0,
            guard_time=0.0,
            repair_used=False,
            deterministic_used=True,
            total_time=total_time,
        )

        source_results = prompt_results
        if str(composition.get("answer_type", "")) == "STANDART / DOKÜMAN":
            source_results = _select_document_source_results(
                reranked_results,
                str(composition.get("primary_answer", "")),
                question=message,
            )

        return {
            "reply": reply,
            "sources": _build_sources(source_results),
            "blocked_sources": _build_blocked_sources(blocked_results),
        }

    fallback_prompt_results: list[dict[str, Any]] = []
    fallback_composition: dict[str, Any] = {}
    fallback_rendered: dict[str, Any] = {}
    fallback_composer_results: list[dict[str, Any]] = []

    if fallback_required:
        print("[FALLBACK] Targeted second-pass retrieval başlıyor.")
        fallback_start = time.perf_counter()
        fallback_results = _targeted_fallback_retrieval(message)
        fallback_time += time.perf_counter() - fallback_start

        if str(composition.get("answer_type", "")) == "STANDART / DOKÜMAN":
            combined_candidates = _deduplicate_results(fallback_results + reranked_results)
            fallback_composer_results = combined_candidates[:DOCUMENT_FALLBACK_COMPOSER_TOP_K]
            fallback_prompt_results = fallback_composer_results[:FALLBACK_COMPOSER_TOP_K]
        else:
            fallback_prompt_results = fallback_results[:FALLBACK_COMPOSER_TOP_K]
            fallback_composer_results = fallback_prompt_results

        print("[FALLBACK] Composer evidence chunk:", len(fallback_composer_results))

        if fallback_composer_results:
            fallback_composer_start = time.perf_counter()
            fallback_composition, fallback_rendered = _compose_and_render(
                question=message,
                chunks=fallback_composer_results,
            )
            composer_time += time.perf_counter() - fallback_composer_start

            print("[FALLBACK COMPOSER] Primary:", fallback_composition.get("primary_answer"))
            print("[FALLBACK COMPOSER] Confidence:", fallback_composition.get("confidence"))

            if _can_use_fast_path(message, fallback_composition, fallback_rendered):
                deterministic_used = True
                reply = str(fallback_rendered.get("reply", ""))
                total_time = time.perf_counter() - total_start
                _print_performance(
                    retrieval_time=retrieval_time,
                    reranker_time=reranker_time,
                    composer_time=composer_time,
                    fallback_time=fallback_time,
                    prompt_time=0.0,
                    ollama_time=0.0,
                    guard_time=0.0,
                    repair_used=False,
                    deterministic_used=True,
                    total_time=total_time,
                )

                source_results = fallback_prompt_results
                if str(fallback_composition.get("answer_type", "")) == "STANDART / DOKÜMAN":
                    source_results = _select_document_source_results(
                        fallback_composer_results,
                        str(fallback_composition.get("primary_answer", "")),
                        question=message,
                    )

                return {
                    "reply": reply,
                    "sources": _build_sources(source_results),
                    "blocked_sources": _build_blocked_sources(blocked_results),
                }

    llm_results = prompt_results
    fallback_confidence = str(fallback_composition.get("confidence", "low"))
    precision_route = (
        _is_reference_point_question(message)
        or bool(_precision_fallback_phrases(message))
        or _is_document_question(message)
    )

    fallback_scores_usable = _fallback_scores_are_usable(fallback_prompt_results)
    fallback_outperforms_normal = _fallback_outperforms_normal_evidence(
        fallback_prompt_results,
        prompt_results,
        question=message,
    )

    if fallback_prompt_results and fallback_scores_usable and not fallback_outperforms_normal:
        print("[EVIDENCE] Normal evidence daha güçlü; fallback kullanılmayacak.")

    precision_fallback_has_evidence = bool(fallback_prompt_results) and precision_route and fallback_scores_usable

    is_nf_intent = any(
        re.search(r"\b" + nf + r"\b", message, flags=re.IGNORECASE)
        for nf in ["amf", "smf", "upf", "ausf", "udm", "pcf", "nssf", "nrf"]
    )

    should_use_fallback = (
        fallback_prompt_results
        and fallback_scores_usable
        and (
            fallback_outperforms_normal
            or is_nf_intent
            or (fallback_confidence in {"medium", "high"})
            or precision_fallback_has_evidence
        )
    )

    if should_use_fallback:
        if str(fallback_composition.get("answer_type", "")) == "STANDART / DOKÜMAN":
            llm_results = _select_document_source_results(
                fallback_composer_results,
                str(fallback_composition.get("primary_answer", "")),
                question=message,
                limit=PROMPT_TOP_K,
            )
        else:
            llm_results = _select_prompt_results(message, fallback_prompt_results)

    precision_route_failed = fallback_required and precision_route and (
        not fallback_prompt_results or not fallback_scores_usable
    )

    evidence_usable = has_usable_evidence(message, llm_results)

    if precision_route_failed or not evidence_usable:
        print(
            "[EVIDENCE GATE] Cevap üretimi durduruldu:",
            "precision fallback kanıt bulamadı" if precision_route_failed else "kanıt yetersiz veya düşük değerli",
        )
        total_time = time.perf_counter() - total_start
        _print_performance(
            retrieval_time=retrieval_time,
            reranker_time=reranker_time,
            composer_time=composer_time,
            fallback_time=fallback_time,
            prompt_time=0.0,
            ollama_time=0.0,
            guard_time=0.0,
            repair_used=False,
            deterministic_used=False,
            total_time=total_time,
        )
        return {
            "reply": "Bu soruyu yanıtlamak için yeterli standart bilgisi bulunamadı.",
            "sources": [],
            "blocked_sources": _build_blocked_sources(blocked_results),
        }

    prompt_start = time.perf_counter()
    user_prompt = build_user_prompt(question=message, chunks=llm_results)
    prompt_time = time.perf_counter() - prompt_start

    print("[PIPELINE] Ollama prompt chunk:", len(llm_results))
    print("[PIPELINE] User prompt karakter:", len(user_prompt))

    ollama_start = time.perf_counter()
    try:
        reply = generate_with_ollama(
            system_prompt=build_system_prompt(message),
            user_prompt=user_prompt,
        )
        ollama_time += time.perf_counter() - ollama_start
    except OllamaServiceError as error:
        ollama_time += time.perf_counter() - ollama_start
        total_time = time.perf_counter() - total_start
        _print_performance(
            retrieval_time=retrieval_time,
            reranker_time=reranker_time,
            composer_time=composer_time,
            fallback_time=fallback_time,
            prompt_time=prompt_time,
            ollama_time=ollama_time,
            guard_time=0.0,
            repair_used=False,
            deterministic_used=False,
            total_time=total_time,
        )
        return {
            "reply": f"Yanıt üretilemedi: {error}",
            "sources": [],
            "blocked_sources": _build_blocked_sources(blocked_results),
        }

    guard_start = time.perf_counter()
    reply = re.sub(r"\b([A-Z][A-Za-z0-9/.-]{1,})\s*\(([^)]+)\)", r"\1", reply)
    validation = validate_answer(question=message, reply=reply, chunks=llm_results)
    guard_time += time.perf_counter() - guard_start

    print("[ANSWER GUARD] İlk cevap:", "PASS" if validation["valid"] else "FAIL")

    if not validation["valid"]:
        print("[ANSWER GUARD] Sebep:", validation.get("reason", ""))
        print("[ANSWER GUARD] Beklenen tür:", validation.get("answer_type", ""))
        print("[ANSWER GUARD] Evidence:", validation.get("evidence_terms", []))

        repair_used = True
        repair_prompt = build_repair_prompt(
            question=message,
            bad_reply=reply,
            chunks=llm_results,
            validation=validation,
        )

        repair_start = time.perf_counter()
        try:
            repaired_reply = generate_with_ollama(
                system_prompt=build_system_prompt(message),
                user_prompt=repair_prompt,
            )
            ollama_time += time.perf_counter() - repair_start
        except OllamaServiceError:
            ollama_time += time.perf_counter() - repair_start
            repaired_reply = ""

        if repaired_reply:
            second_guard_start = time.perf_counter()
            second_validation = validate_answer(
                question=message,
                reply=repaired_reply,
                chunks=llm_results,
            )
            guard_time += time.perf_counter() - second_guard_start
            print("[ANSWER GUARD] Repair cevap:", "PASS" if second_validation["valid"] else "FAIL")

            if second_validation["valid"]:
                reply = repaired_reply
            else:
                print("[ANSWER GUARD] Repair sebep:", second_validation.get("reason", ""))
                reply = build_guard_fallback(second_validation)
        else:
            reply = build_guard_fallback(validation)

    sources = _build_sources(llm_results)
    blocked_sources = _build_blocked_sources(blocked_results)

    total_time = time.perf_counter() - total_start
    _print_performance(
        retrieval_time=retrieval_time,
        reranker_time=reranker_time,
        composer_time=composer_time,
        fallback_time=fallback_time,
        prompt_time=prompt_time,
        ollama_time=ollama_time,
        guard_time=guard_time,
        repair_used=repair_used,
        deterministic_used=deterministic_used,
        total_time=total_time,
    )

    return {
        "reply": reply,
        "sources": sources,
        "blocked_sources": blocked_sources,
    }