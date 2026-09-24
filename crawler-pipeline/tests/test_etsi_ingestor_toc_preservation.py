from chunker import split_into_clauses
from v3_ingestor import (
    _has_reliable_etsi_toc,
    _prepare_document_text,
)


def _etsi_document_with_toc() -> str:
    return """
1 Scope ........................................ 1
2 References ................................... 2
3 Terms ........................................ 3
8.1.6.1 Announcement support .................. 73
8.1.6.2 Announcement switching ................ 74
8.1.6.3 OE Announcement support ............... 75
14 Transmission frame ......................... 110
15 Radio frequency characteristics ........... 118

ETSI

1 Scope
Scope body.

2 References
References body.

3 Terms
Terms body.

8.1.6.1 Announcement support
Support body.

8.1.6.2 Announcement switching
The announcement switching description is encoded in
Extension 19 of FIG type 0 (FIG 0/19).

15 r-15
This is a mathematical table row.

15 logical
This is a figure label.

Figure 43: Structure of announcement switching field.
Cluster Id is defined here.
ASw flags are defined here.
New flag is defined here.
SubChId is defined here.
At the start FIG 0/19 is signalled ten times per second
and then once per second.

8.1.6.3 OE Announcement support
OE support body.

14 Transmission frame
Transmission body.

15 Radio frequency characteristics
Real clause 15 body.
""".strip()


def test_reliable_etsi_toc_is_detected():
    text = _etsi_document_with_toc()

    assert (
        _has_reliable_etsi_toc(
            text
        )
        is True
    )


def test_etsi_preparation_preserves_reliable_toc():
    text = _etsi_document_with_toc()

    prepared = _prepare_document_text(
        "ETSI",
        text,
    )

    assert prepared == text


def test_ingestor_preparation_keeps_toc_guided_clause_integrity():
    text = _etsi_document_with_toc()

    prepared = _prepare_document_text(
        "ETSI",
        text,
    )

    clauses = split_into_clauses(
        document_text=prepared,
        doc_org="ETSI",
    )

    switching = [
        item
        for item in clauses
        if item[0] == "8.1.6.2"
    ]

    assert len(switching) == 1

    _, title, body = switching[0]

    assert title == "Announcement switching"
    assert "Figure 43" in body
    assert "Cluster Id" in body
    assert "ASw" in body
    assert "New flag" in body
    assert "SubChId" in body
    assert "ten times per second" in body
    assert "once per second" in body

    bogus = [
        item
        for item in clauses
        if (
            item[0] == "15"
            and item[1].casefold()
            in {
                "r-15",
                "logical",
            }
        )
    ]

    assert bogus == []

    real_15 = [
        item
        for item in clauses
        if (
            item[0] == "15"
            and item[1]
            == "Radio frequency characteristics"
        )
    ]

    assert len(real_15) == 1


def test_etsi_without_reliable_toc_keeps_legacy_cleanup():
    text = """
[[PAGE:1]]
ETSI
Front matter

1 Scope
Real scope body.
""".strip()

    assert (
        _has_reliable_etsi_toc(
            text
        )
        is False
    )

    prepared = _prepare_document_text(
        "ETSI",
        text,
    )

    assert "[[PAGE:1]]" not in prepared
    assert "Front matter" not in prepared
    assert prepared.startswith(
        "1 Scope"
    )
