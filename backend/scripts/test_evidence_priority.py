from app.services.evidence_priority import (
    prioritize_evidence,
)


def _candidate(
    *,
    org,
    code,
    title,
    text,
    score,
):
    return {
        "text": text,
        "rerank_score": score,
        "metadata": {
            "org": org,
            "code": code,
            "clause_title": title,
            "status": "indexed",
        },
    }


def test_generic_n2_prefers_canonical_definition():
    specific = _candidate(
        org="3GPP",
        code="TS 23.256",
        title="Reference points",
        score=8.0943,
        text=(
            "In addition to the relevant functions "
            "defined in TS 23.501 for N2, in the "
            "case of A2X Service it is also used "
            "to convey A2X Policy."
        ),
    )

    canonical = _candidate(
        org="3GPP",
        code="TS 23.501",
        title="Reference points",
        score=7.9327,
        text=(
            "The 5G System Architecture contains "
            "the following reference points: "
            "N2: Reference point between the "
            "(R)AN and the AMF."
        ),
    )

    ranked = prioritize_evidence(
        (
            "N2 referans noktas? hangi a? "
            "fonksiyonlar? aras?nda kullan?l?r?"
        ),
        [
            specific,
            canonical,
        ],
    )

    assert (
        ranked[0]["metadata"]["code"]
        == "TS 23.501"
    )

    assert [
        item["metadata"]["code"]
        for item in ranked
    ] == [
        "TS 23.501"
    ]


def test_a2x_question_does_not_penalize_extension():
    specific = _candidate(
        org="3GPP",
        code="TS 23.256",
        title="Reference points",
        score=8.0943,
        text=(
            "In addition to the relevant functions "
            "defined in TS 23.501 for N2, in the "
            "case of A2X Service it is also used "
            "to convey A2X Policy."
        ),
    )

    canonical = _candidate(
        org="3GPP",
        code="TS 23.501",
        title="Reference points",
        score=7.9327,
        text=(
            "N2: Reference point between the "
            "(R)AN and the AMF."
        ),
    )

    ranked = prioritize_evidence(
        (
            "A2X Service i?in N2 hangi ek "
            "bilgileri ta??r?"
        ),
        [
            specific,
            canonical,
        ],
    )

    assert (
        ranked[0]["metadata"]["code"]
        == "TS 23.256"
    )


def test_equivalent_http2_clause_prefers_newer_rfc():
    old = _candidate(
        org="IETF",
        code="7540",
        title="Streams and Multiplexing",
        score=-4.5015,
        text=(
            'A "stream" is an independent, '
            "bidirectional sequence of frames "
            "exchanged between the client and "
            "server within an HTTP/2 connection. "
            "A single HTTP/2 connection can contain "
            "multiple concurrently open streams, "
            "with either endpoint interleaving "
            "frames from multiple streams."
        ),
    )

    current = _candidate(
        org="IETF",
        code="9113",
        title="Streams and Multiplexing",
        score=-4.6941,
        text=(
            'A "stream" is an independent, '
            "bidirectional sequence of frames "
            "exchanged between the client and "
            "server within an HTTP/2 connection. "
            "A single HTTP/2 connection can contain "
            "multiple concurrently open streams, "
            "with either endpoint interleaving "
            "frames from multiple streams."
        ),
    )

    ranked = prioritize_evidence(
        (
            "HTTP/2'de birden fazla stream "
            "ayn? ba?lant? ?zerinden nas?l ta??n?r?"
        ),
        [
            old,
            current,
        ],
    )

    assert len(ranked) == 1

    assert (
        ranked[0]["metadata"]["code"]
        == "9113"
    )


def test_unrelated_ietf_documents_are_not_deduplicated():
    first = _candidate(
        org="IETF",
        code="8000",
        title="Introduction",
        score=2.0,
        text=(
            "This document defines protocol alpha "
            "for constrained sensor networks."
        ),
    )

    second = _candidate(
        org="IETF",
        code="9000",
        title="Introduction",
        score=1.0,
        text=(
            "This document specifies a completely "
            "different cryptographic key exchange."
        ),
    )

    ranked = prioritize_evidence(
        "Protocol alpha nedir?",
        [
            first,
            second,
        ],
    )

    assert len(ranked) == 2
    assert (
        ranked[0]["metadata"]["code"]
        == "8000"
    )
