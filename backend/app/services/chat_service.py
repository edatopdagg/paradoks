import time
from typing import Any

from app.services.ollama_service import (
    OllamaServiceError,
    generate_with_ollama,
)
from app.services.prompt_builder import (
    SYSTEM_PROMPT,
    build_user_prompt,
)
from app.services.retriever import Retriever
from app.services.reranker_service import Reranker


# ---------------------------------------------------------
# PIPELINE AYARLARI
# ---------------------------------------------------------

RETRIEVAL_TOP_K = 3

# Ollama'ya en fazla 2 kaynak chunk gönder.
PROMPT_TOP_K = 2


retriever = Retriever()
reranker = Reranker()


def _deduplicate_results(
    results: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Aynı belge/madde/metin tekrarlarını
    reranker öncesinde temizler.
    """

    unique_results: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str, str]] = set()

    for result in results:
        metadata = result.get(
            "metadata",
            {},
        )

        text = (
            result.get("text")
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

        seen.add(key)
        unique_results.append(
            result
        )

    return unique_results


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


def generate_reply(
    message: str,
) -> dict[str, Any]:
    total_start = time.perf_counter()

    # ---------------------------------------------------------
    # RETRIEVAL
    # ---------------------------------------------------------
    retrieval_start = time.perf_counter()

    results = retriever.search(
        query=message,
        top_k=RETRIEVAL_TOP_K,
    )

    retrieval_time = (
        time.perf_counter()
        - retrieval_start
    )

    available_results = [
        result
        for result in results
        if result[
            "metadata"
        ].get(
            "status"
        )
        in {
            "available",
            "indexed",
        }
    ]

    blocked_results = [
        result
        for result in results
        if result[
            "metadata"
        ].get(
            "status"
        )
        == "blocked"
    ]

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

    if not available_results:
        total_time = (
            time.perf_counter()
            - total_start
        )

        print(
            f"[PERF] Retrieval: "
            f"{retrieval_time:.2f} sn"
        )
        print(
            "[PERF] Reranker: 0.00 sn"
        )
        print(
            "[PERF] Prompt: 0.00 sn"
        )
        print(
            "[PERF] Ollama: 0.00 sn"
        )
        print(
            f"[PERF] Total: "
            f"{total_time:.2f} sn"
        )
        print("-" * 50)

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

    # ---------------------------------------------------------
    # RERANKER
    # ---------------------------------------------------------
    reranker_start = (
        time.perf_counter()
    )

    if len(available_results) == 1:
        reranked_results = (
            available_results
        )
    else:
        reranked_results = (
            reranker.rerank(
                query=message,
                candidates=available_results,
            )
        )

    reranker_time = (
        time.perf_counter()
        - reranker_start
    )

    # ---------------------------------------------------------
    # PROMPT İÇİN SON KAYNAKLAR
    # ---------------------------------------------------------
    prompt_results = (
        reranked_results[
            :PROMPT_TOP_K
        ]
    )

    print(
        "[PIPELINE] Prompt'a giden chunk:",
        len(prompt_results),
    )

    # ---------------------------------------------------------
    # PROMPT
    # ---------------------------------------------------------
    prompt_start = (
        time.perf_counter()
    )

    user_prompt = build_user_prompt(
        question=message,
        chunks=prompt_results,
    )

    prompt_time = (
        time.perf_counter()
        - prompt_start
    )

    print(
        "[PIPELINE] User prompt karakter:",
        len(user_prompt),
    )

    # ---------------------------------------------------------
    # OLLAMA
    # ---------------------------------------------------------
    ollama_start = (
        time.perf_counter()
    )

    try:
        reply = generate_with_ollama(
            system_prompt=SYSTEM_PROMPT,
            user_prompt=user_prompt,
        )

        ollama_time = (
            time.perf_counter()
            - ollama_start
        )

    except OllamaServiceError as error:
        ollama_time = (
            time.perf_counter()
            - ollama_start
        )

        total_time = (
            time.perf_counter()
            - total_start
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
            f"[PERF] Prompt: "
            f"{prompt_time:.2f} sn"
        )

        print(
            f"[PERF] Ollama: "
            f"{ollama_time:.2f} sn"
        )

        print(
            f"[PERF] Total: "
            f"{total_time:.2f} sn"
        )

        print("-" * 50)

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

    # ---------------------------------------------------------
    # SOURCES
    # ---------------------------------------------------------
    sources = [
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
        for result in prompt_results
    ]

    blocked_sources = (
        _build_blocked_sources(
            blocked_results
        )
    )

    # ---------------------------------------------------------
    # TOTAL
    # ---------------------------------------------------------
    total_time = (
        time.perf_counter()
        - total_start
    )

    print()
    print("=" * 50)
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
        f"[PERF] Prompt: "
        f"{prompt_time:.2f} sn"
    )

    print(
        f"[PERF] Ollama: "
        f"{ollama_time:.2f} sn"
    )

    print(
        f"[PERF] Total: "
        f"{total_time:.2f} sn"
    )

    print("=" * 50)
    print()

    return {
        "reply": reply,
        "sources": sources,
        "blocked_sources": blocked_sources,
    }