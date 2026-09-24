from app.services.tiered_retriever import (
    _dab_announcement_match_relevance,
)


def _result(
    *,
    code: str,
    clause: str,
    title: str,
    text: str,
):
    return {
        "text": text,
        "distance": 0.15,
        "metadata": {
            "org": "ETSI",
            "code": code,
            "clause": clause,
            "clause_title": title,
        },
    }


def test_normative_switching_clause_is_strongest():
    switching = (
        _dab_announcement_match_relevance(
            _result(
                code="EN 300 401",
                clause="8.1.6.2",
                title="Announcement switching",
                text=(
                    "FIG 0/19 signals announcement switching. "
                    "ASw flags and Cluster Id are defined here."
                ),
            )
        )
    )

    general = (
        _dab_announcement_match_relevance(
            _result(
                code="EN 300 401",
                clause="8.1.6.0",
                title="General",
                text=(
                    "The Announcement feature allows "
                    "interruption. FIG 0/19 is provided."
                ),
            )
        )
    )

    registered_tables = (
        _dab_announcement_match_relevance(
            _result(
                code="TS 101 756",
                clause="59",
                title="ETSI TS 101 756 V2.5.1",
                text=(
                    "Deprecated FIGs include announcement "
                    "switching related definitions."
                ),
            )
        )
    )

    assert switching is not None
    assert general is not None
    assert registered_tables is not None

    assert (
        switching
        > general
        > registered_tables
    )


def test_abbreviations_are_not_direct_dab_evidence():
    result = (
        _dab_announcement_match_relevance(
            _result(
                code="EN 300 401",
                clause="3.3",
                title="Abbreviations",
                text=(
                    "ASu Announcement Support flags "
                    "ASw Announcement Switching flags"
                ),
            )
        )
    )

    assert result is None


def test_switching_identity_does_not_depend_on_text_phrase():
    result = (
        _dab_announcement_match_relevance(
            _result(
                code="EN 300 401",
                clause="8.1.6.2",
                title="Announcement switching",
                text=(
                    "contains the audio service component "
                    "carrying the announcement"
                ),
            )
        )
    )

    assert result == 1000


def test_unrelated_en_clause_with_asw_mention_is_rejected():
    result = (
        _dab_announcement_match_relevance(
            _result(
                code="EN 300 401",
                clause="5.2.2.5",
                title="Summary of available FIGs",
                text=(
                    "Announcement Switching ASw "
                    "FIG information."
                ),
            )
        )
    )

    assert result is None
