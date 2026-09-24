from app.services.evidence_priority import (
    _dab_announcement_direct_bonus,
)


QUESTION = (
    "Digital Audio Broadcasting (DAB) "
    "announcement switching mechanism and "
    "radio receiver switching behavior "
    "according to ETSI standards"
)


def _result(
    code: str,
    text: str,
):
    return {
        "code": code,
        "text": text,
        "metadata": {
            "code": code,
        },
    }


def test_en_300_401_gets_strongest_direct_bonus():
    en = _dab_announcement_direct_bonus(
        question=QUESTION,
        result=_result(
            "EN 300 401",
            (
                "Figure 43: Structure of announcement "
                "switching field. ASw flags. FIG 0/19."
            ),
        ),
    )

    registered_tables = (
        _dab_announcement_direct_bonus(
            question=QUESTION,
            result=_result(
                "TS 101 756",
                (
                    "Announcement Switching definitions "
                    "refer to ETSI EN 300 401."
                ),
            ),
        )
    )

    assert en > registered_tables
    assert en > 0


def test_service_following_gets_no_dab_announcement_bonus():
    bonus = _dab_announcement_direct_bonus(
        question=QUESTION,
        result=_result(
            "TS 102 818",
            (
                "DAB service following provides "
                "alternative bearers and bearer matching."
            ),
        ),
    )

    assert bonus == 0.0


def test_non_dab_query_gets_no_bonus():
    bonus = _dab_announcement_direct_bonus(
        question=(
            "Explain HTTP PUT and PATCH."
        ),
        result=_result(
            "EN 300 401",
            "Announcement Switching FIG 0/19",
        ),
    )

    assert bonus == 0.0
