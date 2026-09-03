import re
from typing import Any
from uuid import uuid4

from app.services.conversation_memory import (
    append_turn,
    get_recent_turns,
)
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



def _needs_conversation_context(
    question: str,
) -> bool:
    value = (
        question
        or ""
    ).strip().casefold()

    if not value:
        return False

    follow_up_starts = (
        "peki ",
        "peki bunun",
        "peki bu",
        "ya bunun",
        "ya bu",
        "bunun ",
        "bunu ",
        "buna ",
        "bundan ",
        "onun ",
        "onu ",
        "ona ",
        "what about ",
        "how about ",
        "and what ",
        "and how ",
    )

    if value.startswith(
        follow_up_starts
    ):
        return True

    pronoun_pattern = re.compile(
        (
            r"\b("
            r"bu|bunun|bunu|buna|bunda|bundan|"
            r"o|onun|onu|ona|aynı|"
            r"this|that|it|its|these|those|same"
            r")\b"
        ),
        flags=re.IGNORECASE,
    )

    return bool(
        pronoun_pattern.search(
            value
        )
    )


def _build_contextual_question(
    question: str,
    turns,
    *,
    language: str,
) -> str:
    if (
        not turns
        or not _needs_conversation_context(
            question
        )
    ):
        return question

    context_parts: list[str] = []

    for turn in turns:
        user_message = (
            turn.user_message
            or ""
        ).strip()

        assistant_message = (
            turn.assistant_message
            or ""
        ).strip()

        if user_message:
            context_parts.append(
                user_message
            )

        if assistant_message:
            context_parts.append(
                assistant_message
            )

    if not context_parts:
        return question

    context = " ".join(
        context_parts
    )

    # Retrieval sorgusunun gereksiz büyümesini engelle.
    context = context[
        -3000:
    ]

    if language == "en":
        return (
            f"{question}\n\n"
            f"Previous conversation context: "
            f"{context}"
        )

    return (
        f"{question}\n\n"
        f"Önceki konuşma bağlamı: "
        f"{context}"
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

    recent_turns = get_recent_turns(
        resolved_conversation_id,
        limit=2,
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
        retrieval_question = (
            _build_contextual_question(
                planned_question.text,
                recent_turns,
                language=plan.language,
            )
        )

        result = generate_reply(
            retrieval_question
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

    append_turn(
        resolved_conversation_id,
        user_message=message,
        assistant_message=standard_answer,
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