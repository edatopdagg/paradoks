import re
from dataclasses import dataclass


@dataclass(frozen=True)
class PlannedQuestion:
    text: str
    intent: str


@dataclass(frozen=True)
class QuestionPlan:
    language: str
    questions: list[PlannedQuestion]


_TURKISH_CHARACTERS = set(
    "çğıöşüÇĞİÖŞÜ"
)

_TURKISH_WORDS = {
    "hangi",
    "nedir",
    "neden",
    "nasıl",
    "ne",
    "kaç",
    "üzerinden",
    "arasındaki",
    "taşınır",
    "kullanılır",
    "görevi",
    "amacı",
}

_ENGLISH_WORDS = {
    "which",
    "what",
    "why",
    "how",
    "where",
    "when",
    "does",
    "is",
    "are",
    "carried",
    "over",
    "between",
    "purpose",
}

_COMPOUND_QUESTION_SPLIT = re.compile(
    r"\s+(?:ve|and)\s+"
    r"(?=(?:\S+\s+){0,4}"
    r"(?:neden|nasıl|hangi|ne|kaç|kim|nerede|"
    r"why|how|which|what|who|where|when)\b)",
    flags=re.IGNORECASE,
)


def _normalize_space(
    value: str,
) -> str:
    return re.sub(
        r"\s+",
        " ",
        (value or "").strip(),
    )


def detect_language(
    text: str,
) -> str:
    value = _normalize_space(text)

    if any(
        character in _TURKISH_CHARACTERS
        for character in value
    ):
        return "tr"

    tokens = set(
        re.findall(
            r"[A-Za-zÀ-ž]+",
            value.casefold(),
        )
    )

    turkish_score = len(
        tokens & _TURKISH_WORDS
    )

    english_score = len(
        tokens & _ENGLISH_WORDS
    )

    if english_score > turkish_score:
        return "en"

    return "tr"


def _split_questions(
    text: str,
) -> list[str]:
    value = _normalize_space(text)

    if not value:
        return []

    sentence_parts = [
        part.strip(" ;?")
        for part in re.split(
            r"\?+\s*|\s*;\s*",
            value,
        )
        if part.strip(" ;?")
    ]

    questions: list[str] = []

    for sentence_part in sentence_parts:
        compound_parts = (
            _COMPOUND_QUESTION_SPLIT.split(
                sentence_part
            )
        )

        questions.extend(
            part.strip(" ;?")
            for part in compound_parts
            if part.strip(" ;?")
        )

    return questions or [
        value.strip(" ;?")
    ]


def _infer_intent(
    question: str,
) -> str:
    value = _normalize_space(
        question
    ).casefold()

    purpose_markers = (
        "ne işe yar",
        "amacı",
        "hangi amaçla",
        "ne amaçla",
        "görevi",
        "neden kullan",
        "what is the purpose",
        "what does",
    )

    if any(
        marker in value
        for marker in purpose_markers
    ):
        return "purpose"

    if re.search(
        r"\b(?:hangisi\w*|which)\b",
        value,
    ):
        return "identity"

    if any(
        marker in value
        for marker in (
            "karşılaştır",
            "farkı",
            "compare",
            "difference",
        )
    ):
        return "comparison"

    if any(
        marker in value
        for marker in (
            "neden",
            "niçin",
            "why",
        )
    ):
        return "explanation"

    if any(
        marker in value
        for marker in (
            "nasıl",
            "how",
        )
    ):
        return "mechanism"

    if re.search(
        r"\b(?:kaç|maximum|minimum|maksimum|"
        r"how many|how much)\b",
        value,
    ):
        return "value"

    if re.search(
        r"\b(?:nedir|what is|define)\b",
        value,
    ):
        return "definition"

    return "general"


def build_question_plan(
    message: str,
) -> QuestionPlan:
    language = detect_language(
        message
    )

    question_texts = _split_questions(
        message
    )

    return QuestionPlan(
        language=language,
        questions=[
            PlannedQuestion(
                text=question_text,
                intent=_infer_intent(
                    question_text
                ),
            )
            for question_text in question_texts
        ],
    )