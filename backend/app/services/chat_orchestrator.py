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
    domain: str = "telecom",
) -> dict[str, Any]:
    """
    Mevcut RAG hattını yalnızca gerçek bir
    cevap çağrısı yapıldığında yükler.
    """

    from app.services.chat_service import (
        generate_reply as legacy_generate_reply,
    )

    return legacy_generate_reply(
        message,
        domain=domain,
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
    """
    Only explicit follow-up wording may pull previous
    conversation text into retrieval.

    Words such as "ayni/same" in the middle of an otherwise
    independent technical question must not activate memory.
    """

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
        "bunda ",
        "bundan ",
        "bu ",
        "onun ",
        "onu ",
        "ona ",
        "o ",
        "ayn\u0131 ",
        "what about ",
        "how about ",
        "and what ",
        "and how ",
        "this ",
        "that ",
        "it ",
        "its ",
        "these ",
        "those ",
        "same ",
    )

    if value.startswith(
        follow_up_starts
    ):
        return True

    short_follow_ups = {
        "neden",
        "neden?",
        "ni\u00e7in",
        "ni\u00e7in?",
        "nas\u0131l",
        "nas\u0131l?",
        "why",
        "why?",
        "how",
        "how?",
        "hangisi",
        "hangisi?",
        "which one",
        "which one?",
    }

    return value in short_follow_ups

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

        assistant_normalized = (
            assistant_message.casefold()
        )

        if (
            assistant_message
            and "yeterli standart bilgisi bulunamad"
            not in assistant_normalized
            and "not enough standard information"
            not in assistant_normalized
        ):
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
    domain: str = "telecom",
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
            retrieval_question,
            domain=domain,
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
