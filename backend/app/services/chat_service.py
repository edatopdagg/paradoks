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
    results = retriever.search(
        query=message,
        top_k=5,
    )

    available_results = [
        result
        for result in results
        if result["metadata"].get("status") == "available"
    ]

    blocked_results = [
        result
        for result in results
        if result["metadata"].get("status") == "blocked"
    ]

    if not available_results:
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

    reranked_results = reranker.rerank(
    query=message,
    candidates=available_results,
)

    user_prompt = build_user_prompt(
    question=message,
    chunks=reranked_results,
)
    try:
        reply = generate_with_ollama(
            system_prompt=SYSTEM_PROMPT,
            user_prompt=user_prompt,
        )

    except OllamaServiceError as error:
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

    return {
        "reply": reply,
        "sources": sources,
        "blocked_sources": blocked_sources,
    }