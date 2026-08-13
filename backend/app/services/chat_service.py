import time
from typing import Any

from app.services.ollama_service import (
    OllamaServiceError,
    generate_with_ollama,
)

from app.services.prompt_builder import SYSTEM_PROMPT, build_user_prompt
from app.services.retriever import Retriever
from app.services.reranker_service import Reranker


retriever = Retriever()
reranker = Reranker()


def generate_reply(message: str) -> dict[str, Any]:
    total_start = time.perf_counter()

    # ---------------------------------------------------------
    # RETRIEVAL
    # Şimdilik embedding + Chroma search bu sürenin içinde.
    # ---------------------------------------------------------
    retrieval_start = time.perf_counter()

    results = retriever.search(
        query=message,
        top_k=5,
    )

    retrieval_time = time.perf_counter() - retrieval_start

    available_results = [
        result
        for result in results
        if result["metadata"].get("status")
        in {"available", "indexed"}
    ]

    blocked_results = [
        result
        for result in results
        if result["metadata"].get("status") == "blocked"
    ]

    if not available_results:
        total_time = time.perf_counter() - total_start

        print(f"[PERF] Retrieval: {retrieval_time:.2f} sn")
        print("[PERF] Reranker: 0.00 sn")
        print("[PERF] Prompt: 0.00 sn")
        print("[PERF] Ollama: 0.00 sn")
        print(f"[PERF] Total: {total_time:.2f} sn")
        print("-" * 50)

        return {
            "reply": (
                "Bu soruyu yanıtlamak için erişilebilir "
                "bir standart maddesi bulunamadı."
            ),
            "sources": [],
            "blocked_sources": [
                {
                    "org": result["metadata"].get("org", "Bilinmiyor"),
                    "code": result["metadata"].get("code", "Bilinmiyor"),
                    "source_url": result["metadata"].get("source_url", ""),
                }
                for result in blocked_results
            ],
        }

    # ---------------------------------------------------------
    # RERANKER
    # ---------------------------------------------------------
    reranker_start = time.perf_counter()

    reranked_results = reranker.rerank(
        query=message,
        candidates=available_results,
    )

    reranker_time = time.perf_counter() - reranker_start

    # ---------------------------------------------------------
    # PROMPT
    # ---------------------------------------------------------
    prompt_start = time.perf_counter()

    user_prompt = build_user_prompt(
        question=message,
        chunks=reranked_results,
    )

    prompt_time = time.perf_counter() - prompt_start

    # ---------------------------------------------------------
    # OLLAMA
    # ---------------------------------------------------------
    ollama_start = time.perf_counter()

    try:
        reply = generate_with_ollama(
            system_prompt=SYSTEM_PROMPT,
            user_prompt=user_prompt,
        )

        ollama_time = time.perf_counter() - ollama_start

    except OllamaServiceError as error:
        ollama_time = time.perf_counter() - ollama_start
        total_time = time.perf_counter() - total_start

        print(f"[PERF] Retrieval: {retrieval_time:.2f} sn")
        print(f"[PERF] Reranker: {reranker_time:.2f} sn")
        print(f"[PERF] Prompt: {prompt_time:.2f} sn")
        print(f"[PERF] Ollama: {ollama_time:.2f} sn")
        print(f"[PERF] Total: {total_time:.2f} sn")
        print("-" * 50)

        return {
            "reply": f"Yanıt üretilemedi: {error}",
            "sources": [],
            "blocked_sources": [
                {
                    "org": result["metadata"].get("org", "Bilinmiyor"),
                    "code": result["metadata"].get("code", "Bilinmiyor"),
                    "source_url": result["metadata"].get("source_url", ""),
                }
                for result in blocked_results
            ],
        }

    sources = [
        {
            "org": result["metadata"].get("org", "Bilinmiyor"),
            "code": result["metadata"].get("code", "Bilinmiyor"),
            "version": result["metadata"].get("version", "Bilinmiyor"),
            "clause": result["metadata"].get("clause", "Bilinmiyor"),
            "status": result["metadata"].get("status", "Bilinmiyor"),
            "source_url": result["metadata"].get("source_url", ""),
            "distance": result["distance"],
        }
        for result in reranked_results
    ]

    blocked_sources = [
        {
            "org": result["metadata"].get("org", "Bilinmiyor"),
            "code": result["metadata"].get("code", "Bilinmiyor"),
            "source_url": result["metadata"].get("source_url", ""),
        }
        for result in blocked_results
    ]

    # ---------------------------------------------------------
    # TOTAL
    # ---------------------------------------------------------
    total_time = time.perf_counter() - total_start

    print()
    print("=" * 50)
    print("[PERF] Paradoks Pipeline")
    print(f"[PERF] Retrieval: {retrieval_time:.2f} sn")
    print(f"[PERF] Reranker: {reranker_time:.2f} sn")
    print(f"[PERF] Prompt: {prompt_time:.2f} sn")
    print(f"[PERF] Ollama: {ollama_time:.2f} sn")
    print(f"[PERF] Total: {total_time:.2f} sn")
    print("=" * 50)
    print()

    return {
        "reply": reply,
        "sources": sources,
        "blocked_sources": blocked_sources,
    }