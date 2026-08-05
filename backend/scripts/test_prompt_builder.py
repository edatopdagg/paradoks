from app.services.prompt_builder import (
    SYSTEM_PROMPT,
    build_user_prompt,
)
from app.services.retriever import Retriever


def main() -> None:
    question = "Cell Broadcast warning mesajı nasıl iptal edilir?"

    retriever = Retriever()
    results = retriever.search(
        query=question,
        top_k=3,
    )

    available_results = [
        result
        for result in results
        if result["metadata"].get("status") == "available"
    ]

    user_prompt = build_user_prompt(
        question=question,
        chunks=available_results,
    )

    print("SYSTEM PROMPT")
    print("=" * 70)
    print(SYSTEM_PROMPT)

    print("\nUSER PROMPT")
    print("=" * 70)
    print(user_prompt)


if __name__ == "__main__":
    main()