from app.services.answer_guard import (
    validate_answer,
)


def _rds_chunk(text: str):
    return {
        "text": text,
        "metadata": {
            "org": "NRSC",
            "code": "NRSC-G300-C",
            "clause": "5.4",
            "clause_title": (
                "Traffic programming (TP)/"
                "Traffic Announcement (TA) flags"
            ),
        },
    }


def test_rds_positive_rewrite_of_discouraged_claim_fails():
    question = (
        "RDS/RBDS sisteminde Traffic Programme (TP) "
        "ve Traffic Announcement (TA) flag'leri "
        "ne i\u015fe yarar?"
    )

    chunks = [
        _rds_chunk(
            "Automatic receiver switching using "
            "the Traffic Announcement (TA) flag "
            "is discouraged."
        )
    ]

    reply = (
        "Traffic Announcement (TA) flag, "
        "trafik anonsu s\u0131ras\u0131nda "
        "al\u0131c\u0131y\u0131 otomatik olarak "
        "ilgili yay\u0131na ge\u00e7irir."
    )

    result = validate_answer(
        question=question,
        reply=reply,
        chunks=chunks,
    )

    assert not result["valid"]
    assert "normatif" in result["reason"]


def test_rds_discouraged_claim_preserved_passes():
    question = (
        "RDS/RBDS sisteminde Traffic Programme (TP) "
        "ve Traffic Announcement (TA) flag'leri "
        "ne i\u015fe yarar?"
    )

    chunks = [
        _rds_chunk(
            "Automatic receiver switching using "
            "the Traffic Announcement (TA) flag "
            "is discouraged."
        )
    ]

    reply = (
        "Traffic Announcement (TA) flag otomatik "
        "al\u0131c\u0131 ge\u00e7i\u015fiyle "
        "ili\u015fkilidir; ancak NRSC bu "
        "kullan\u0131m\u0131n tercih edilmesini "
        "\u00f6nermemektedir."
    )

    result = validate_answer(
        question=question,
        reply=reply,
        chunks=chunks,
    )

    assert result["valid"]


def test_repeated_http2_sentence_fails():
    question = (
        "HTTP/2'de birden fazla stream ayn\u0131 "
        "ba\u011flant\u0131 \u00fczerinden "
        "nas\u0131l ta\u015f\u0131n\u0131r?"
    )

    chunks = [
        {
            "text": (
                "A single HTTP/2 connection can "
                "contain multiple concurrent streams. "
                "Frames from multiple streams can be "
                "interleaved on the connection."
            ),
            "metadata": {
                "org": "IETF",
                "code": "9113",
                "clause": "5",
                "clause_title": (
                    "Streams and Multiplexing"
                ),
            },
        }
    ]

    sentence = (
        "HTTP/2 tek bir ba\u011flant\u0131 "
        "\u00fczerinde birden fazla stream'i "
        "multiplexing ile ta\u015f\u0131r ve "
        "farkl\u0131 stream'lere ait frame'ler "
        "birbirine kar\u0131\u015ft\u0131r\u0131larak "
        "iletilebilir."
    )

    reply = (
        sentence
        + " "
        + sentence
    )

    result = validate_answer(
        question=question,
        reply=reply,
        chunks=chunks,
    )

    assert not result["valid"]
    assert "tekrar" in result["reason"]


def test_short_non_repeated_http2_answer_passes():
    question = (
        "HTTP/2'de birden fazla stream ayn\u0131 "
        "ba\u011flant\u0131 \u00fczerinden "
        "nas\u0131l ta\u015f\u0131n\u0131r?"
    )

    chunks = [
        {
            "text": (
                "A single HTTP/2 connection can "
                "contain multiple concurrent streams. "
                "Frames from multiple streams can be "
                "interleaved on the connection."
            ),
            "metadata": {
                "org": "IETF",
                "code": "9113",
                "clause": "5",
                "clause_title": (
                    "Streams and Multiplexing"
                ),
            },
        }
    ]

    reply = (
        "HTTP/2, ayn\u0131 ba\u011flant\u0131 "
        "\u00fczerindeki birden fazla stream'e "
        "ait frame'leri interleaving yaparak "
        "ta\u015f\u0131r."
    )

    result = validate_answer(
        question=question,
        reply=reply,
        chunks=chunks,
    )

    assert result["valid"]
