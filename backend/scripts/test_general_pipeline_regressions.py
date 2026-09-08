from app.services.chat_orchestrator import (
    _needs_conversation_context,
)
from app.services.question_planner import (
    build_question_plan,
)
from app.services import chat_service


def test_http2_same_connection_does_not_activate_memory():
    question = (
        "HTTP/2'de birden fazla stream "
        "ayn\u0131 ba\u011flant\u0131 \u00fczerinden "
        "nas\u0131l ta\u015f\u0131n\u0131r?"
    )

    assert not _needs_conversation_context(
        question
    )


def test_real_follow_up_still_activates_memory():
    assert _needs_conversation_context(
        "Peki bunun temel g\u00f6revi nedir?"
    )


def test_rds_tp_ta_stays_one_question():
    question = (
        "RDS/RBDS sisteminde Traffic Programme (TP) "
        "ve Traffic Announcement (TA) flag'leri "
        "ne i\u015fe yarar?"
    )

    plan = build_question_plan(
        question
    )

    assert len(plan.questions) == 1
    assert "Traffic Programme" in plan.questions[0].text
    assert "Traffic Announcement" in plan.questions[0].text


def test_existing_true_compound_question_still_splits():
    question = (
        "N1 \u00fczerinden hangi sinyalle\u015fme ta\u015f\u0131n\u0131r "
        "ve bu sinyalle\u015fme neden NAS olarak adland\u0131r\u0131l\u0131r?"
    )

    plan = build_question_plan(
        question
    )

    assert len(plan.questions) == 2


def test_n2_strong_relation_can_recover_without_fts():
    candidate = {
        "text": (
            "N2: The reference point between "
            "the (R)AN and the AMF."
        ),
        "metadata": {
            "org": "3GPP",
            "code": "TS 23.501",
            "clause": "4.2.7",
            "clause_title": "Reference points",
        },
        "distance": 0.23,
        "rerank_score": 7.93,
    }

    selected = (
        chat_service
        ._recover_reference_point_semantic_candidates(
            (
                "N2 referans noktas\u0131 hangi a\u011f "
                "fonksiyonlar\u0131 aras\u0131nda kullan\u0131l\u0131r "
                "ve temel g\u00f6revi nedir?"
            ),
            [candidate],
        )
    )

    assert selected
    assert (
        selected[0]["metadata"]["clause"]
        == "4.2.7"
    )


def test_bare_reference_point_definition_does_not_recover():
    candidate = {
        "text": (
            "N3 is a reference point "
            "in the 5G System."
        ),
        "metadata": {
            "org": "3GPP",
            "code": "TS 24.554",
            "clause": "8.2.6.4.1",
            "clause_title": "General",
        },
        "distance": 0.20,
        "rerank_score": 9.0,
    }

    selected = (
        chat_service
        ._recover_reference_point_semantic_candidates(
            (
                "N3 referans noktas\u0131n\u0131n "
                "5G mimarisindeki g\u00f6revi nedir?"
            ),
            [candidate],
        )
    )

    assert selected == []
