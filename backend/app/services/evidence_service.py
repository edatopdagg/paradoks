import time
from typing import Any

from app.services.chat_service import (
    RETRIEVAL_TOP_K,
    _build_blocked_sources,
    _deduplicate_results,
    _filter_available_results,
    _filter_blocked_results,
    _prefer_content_results,
    _select_prompt_results,
    build_chroma_where,
    extract_document_constraint,
    result_matches_document_constraint,
    retriever,
    reranker,
)
from app.services.source_service import (
    get_source_clause,
)


def _safe_float(
    value: Any,
    default: float = 1.0,
) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_page(
    value: Any,
) -> int | None:
    try:
        number = int(value)

        if number < 0:
            return None

        return number

    except (TypeError, ValueError):
        return None


def _load_exact_clause_text(
    *,
    version_id: str,
    clause_id: str,
) -> str:
    """
    Exact source viewer'ın kullandığı aynı V3 clause kaydından
    gerçek madde metnini getirir.

    Evidence endpoint böylece Gemini'ye yalnızca metadata değil,
    gerçek standart metnini de sağlar.
    """

    if not version_id or not clause_id:
        return ""

    try:

        clause = get_source_clause(
            version_id=version_id,
            clause_id=clause_id,
        )

    except (
        FileNotFoundError,
        KeyError,
    ):
        return ""

    return str(
        clause.get(
            "body_text",
            "",
        )
        or ""
    ).strip()


def _source_from_result(
    result: dict[str, Any],
) -> dict[str, Any]:
    """
    Retriever/reranker sonucunu mevcut Paradoks Source
    sözleşmesine dönüştürür.

    Burada LLM çağrısı yapılmaz.
    """

    metadata = (
        result.get("metadata")
        or {}
    )

    version_id = str(
        metadata.get(
            "version_id",
            "",
        )
        or ""
    )

    clause_id = str(
        metadata.get(
            "clause_id",
            "",
        )
        or ""
    )

    viewer_url = str(
        metadata.get(
            "viewer_url",
            "",
        )
        or ""
    )

    if (
        not viewer_url
        and version_id
        and clause_id
    ):
        viewer_url = (
            f"/sources/{version_id}"
            f"/clauses/{clause_id}"
        )

    exact_clause_text = (
        _load_exact_clause_text(
            version_id=version_id,
            clause_id=clause_id,
        )
    )

    if not exact_clause_text:

        exact_clause_text = str(
            metadata.get(
                "highlight_text",
                "",
            )
            or result.get(
                "document",
                "",
            )
            or result.get(
                "text",
                "",
            )
            or ""
        ).strip()

    source_id = str(
        metadata.get(
            "source_id",
            "",
        )
        or result.get(
            "id",
            "",
        )
        or ""
    )

    return {
        "org": str(
            metadata.get(
                "org",
                "",
            )
            or ""
        ),
        "code": str(
            metadata.get(
                "code",
                "",
            )
            or ""
        ),
        "version": str(
            metadata.get(
                "version",
                "",
            )
            or ""
        ),
        "clause": str(
            metadata.get(
                "clause",
                "",
            )
            or ""
        ),
        "clause_title": str(
            metadata.get(
                "clause_title",
                "",
            )
            or ""
        ),
        "status": str(
            metadata.get(
                "status",
                "indexed",
            )
            or "indexed"
        ),
        "source_url": str(
            metadata.get(
                "source_url",
                "",
            )
            or ""
        ),
        "distance": _safe_float(
            result.get(
                "distance",
                1.0,
            )
        ),
        "source_id": source_id,
        "document_id": str(
            metadata.get(
                "document_id",
                "",
            )
            or ""
        ),
        "version_id": version_id,
        "clause_id": clause_id,
        "page_number": _safe_page(
            metadata.get(
                "page_number"
            )
        ),
        "page_start": _safe_page(
            metadata.get(
                "page_start"
            )
        ),
        "page_end": _safe_page(
            metadata.get(
                "page_end"
            )
        ),
        "viewer_url": viewer_url,
        "local_path": str(
            metadata.get(
                "local_path",
                "",
            )
            or ""
        ),
        "highlight_text": (
            exact_clause_text
        ),
        "char_start": metadata.get(
            "char_start"
        ),
        "char_end": metadata.get(
            "char_end"
        ),
    }


def generate_evidence(
    message: str,
    domain: str = "telecom",
) -> dict[str, Any]:
    """
    Paradoks'un LLM'siz evidence hattı.

    Akış:

        soru
          -> document constraint
          -> tiered retrieval
          -> availability / dedupe
          -> exact document validation
          -> reranker
          -> en güçlü evidence
          -> exact clause body
          -> source metadata

    Bilerek yapılmayanlar:

        - Ollama çağrısı
        - prompt oluşturma
        - answer generation
        - answer guard / repair

    Son cevabı ISTLINK / Gemini üretecektir.
    """

    started = time.perf_counter()

    clean_message = (
        message
        or ""
    ).strip()

    if not clean_message:
        raise ValueError(
            "Evidence sorgusu boş olamaz."
        )

    clean_domain = (
        domain
        or "telecom"
    ).strip().casefold()

    if clean_domain not in {
        "telecom",
        "radio",
    }:
        raise ValueError(
            "Geçersiz evidence domain."
        )

    document_constraint = (
        extract_document_constraint(
            clean_message
        )
    )

    retrieval_where = (
        build_chroma_where(
            document_constraint
        )
    )

    retrieval_started = (
        time.perf_counter()
    )

    results = retriever.search(
        query=clean_message,
        top_k=RETRIEVAL_TOP_K,
        where=retrieval_where,
        domain=clean_domain,
    )

    retrieval_ms = (
        time.perf_counter()
        - retrieval_started
    ) * 1000.0

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

    if document_constraint:
        available_results = [
            result
            for result in available_results
            if result_matches_document_constraint(
                result,
                document_constraint,
            )
        ]

    available_results = (
        _prefer_content_results(
            clean_message,
            available_results,
        )
    )

    if not available_results:

        total_ms = (
            time.perf_counter()
            - started
        ) * 1000.0

        return {
            "query": clean_message,
            "domain": clean_domain,
            "evidence": [],
            "blocked_sources": (
                _build_blocked_sources(
                    blocked_results
                )
            ),
            "retrieval_ms": retrieval_ms,
            "reranker_ms": 0.0,
            "total_ms": total_ms,
        }

    reranker_started = (
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
                query=clean_message,
                candidates=(
                    available_results
                ),
                top_k=len(
                    available_results
                ),
            )
        )

    reranker_ms = (
        time.perf_counter()
        - reranker_started
    ) * 1000.0

    evidence_results = (
        _select_prompt_results(
            clean_message,
            reranked_results,
        )
    )

    evidence = [
        _source_from_result(
            result
        )
        for result in evidence_results
    ]

    total_ms = (
        time.perf_counter()
        - started
    ) * 1000.0

    print()
    print("=" * 60)
    print("[EVIDENCE API]")

    print(
        "[EVIDENCE] Query:",
        clean_message,
    )

    print(
        "[EVIDENCE] Domain:",
        clean_domain,
    )

    print(
        "[EVIDENCE] Retrieval:",
        f"{retrieval_ms:.2f} ms",
    )

    print(
        "[EVIDENCE] Reranker:",
        f"{reranker_ms:.2f} ms",
    )

    print(
        "[EVIDENCE] Result count:",
        len(evidence),
    )

    print(
        "[EVIDENCE] Exact text:",
        sum(
            1
            for source in evidence
            if source.get(
                "highlight_text"
            )
        ),
        "/",
        len(evidence),
    )

    print(
        "[EVIDENCE] Total:",
        f"{total_ms:.2f} ms",
    )

    print(
        "[EVIDENCE] Ollama:",
        "BYPASSED",
    )

    print("=" * 60)
    print()

    return {
        "query": clean_message,
        "domain": clean_domain,
        "evidence": evidence,
        "blocked_sources": (
            _build_blocked_sources(
                blocked_results
            )
        ),
        "retrieval_ms": retrieval_ms,
        "reranker_ms": reranker_ms,
        "total_ms": total_ms,
    }