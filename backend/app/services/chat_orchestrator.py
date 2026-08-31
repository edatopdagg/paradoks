from typing import Any
from uuid import uuid4

from app.services.question_planner import (
    build_question_plan,
)


def generate_reply(
    message: str,
) -> dict[str, Any]:
    """
    Mevcut RAG hattını yalnızca gerçek bir
    cevap çağrısı yapıldığında yükler.
    """

    from app.services.chat_service import (
        generate_reply as legacy_generate_reply,
    )

    return legacy_generate_reply(
        message
    )


def _source_key(
    source: dict[str, Any],
) -> tuple[str, ...]:
    source_id = str(
        source.get(
            "source_id",
            "",
        )
        or ""
    ).strip()

    if source_id:
        return (
            "source_id",
            source_id,
        )

    return (
        "metadata",
        str(
            source.get("org", "")
            or ""
        ).casefold(),
        str(
            source.get("code", "")
            or ""
        ).casefold(),
        str(
            source.get("version", "")
            or ""
        ).casefold(),
        str(
            source.get("clause", "")
            or ""
        ).casefold(),
        str(
            source.get("source_url", "")
            or ""
        ).casefold(),
    )


def _blocked_source_key(
    source: dict[str, Any],
) -> tuple[str, ...]:
    return (
        str(
            source.get("org", "")
            or ""
        ).casefold(),
        str(
            source.get("code", "")
            or ""
        ).casefold(),
        str(
            source.get("source_url", "")
            or ""
        ).casefold(),
    )


def _append_unique(
    target: list[dict[str, Any]],
    seen: set[tuple[str, ...]],
    values: list[dict[str, Any]],
    key_builder,
) -> None:
    for value in values:
        key = key_builder(
            value
        )

        if key in seen:
            continue

        seen.add(
            key
        )

        target.append(
            value
        )


def _combine_answers(
    answers: list[str],
) -> str:
    clean_answers = [
        answer.strip()
        for answer in answers
        if answer.strip()
    ]

    if not clean_answers:
        return ""

    if len(clean_answers) == 1:
        return clean_answers[0]

    return "\n\n".join(
        f"{index}. {answer}"
        for index, answer in enumerate(
            clean_answers,
            start=1,
        )
    )


def generate_chat_response(
    message: str,
    conversation_id: str | None = None,
) -> dict[str, Any]:
    plan = build_question_plan(
        message
    )

    resolved_conversation_id = (
        conversation_id
        or str(uuid4())
    )

    answers: list[str] = []

    planned_questions: list[
        dict[str, Any]
    ] = []

    sources: list[
        dict[str, Any]
    ] = []

    blocked_sources: list[
        dict[str, Any]
    ] = []

    seen_sources: set[
        tuple[str, ...]
    ] = set()

    seen_blocked_sources: set[
        tuple[str, ...]
    ] = set()

    for planned_question in plan.questions:
        result = generate_reply(
            planned_question.text
        )

        answer = str(
            result.get(
                "reply",
                "",
            )
            or ""
        ).strip()

        question_sources = list(
            result.get(
                "sources",
                [],
            )
            or []
        )

        answers.append(
            answer
        )

        planned_questions.append(
            {
                "text": planned_question.text,
                "intent": planned_question.intent,
                "answered": bool(
                    answer
                    and question_sources
                ),
            }
        )

        _append_unique(
            sources,
            seen_sources,
            question_sources,
            _source_key,
        )

        _append_unique(
            blocked_sources,
            seen_blocked_sources,
            list(
                result.get(
                    "blocked_sources",
                    [],
                )
                or []
            ),
            _blocked_source_key,
        )

    standard_answer = _combine_answers(
        answers
    )

    return {
        "conversation_id": (
            resolved_conversation_id
        ),
        "detected_language": (
            plan.language
        ),
        "questions": (
            planned_questions
        ),
        "standard_answer": (
            standard_answer
        ),
        "assistant_answer": "",
        "reply": standard_answer,
        "sources": sources,
        "blocked_sources": (
            blocked_sources
        ),
    }