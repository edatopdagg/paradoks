from chunker import (
    _split_etsi_clauses,
)


def test_etsi_toc_guidance_rejects_numeric_figure_artifacts():
    text = """
1 Scope ........................................ 1
8.1.6.2 Announcement switching ............... 74
8.1.6.3 OE Announcement support .............. 75
14 Transmission frame ........................ 110
15 Radio frequency characteristics .......... 118
15.1 Use of the transmission mode ............ 118
16 Final section .............................. 120

1 Scope
Scope body.

8.1.6.2 Announcement switching
The announcement switching description uses FIG 0/19.

15 b10 90 7 15
Figure 43: Structure of announcement switching field.
Cluster Id is encoded here.
ASw flags are encoded here.
New flag is encoded here.
SubChId is encoded here.
At the start it is sent ten times per second.

8.1.6.3 OE Announcement support
Next real clause.

14 Transmission frame
Transmission-frame body.

15 r-15
This is a mathematical table row.

15 logical
This is a figure label.

15 MOT, continuation of CA messages
This is a table entry.

15 Radio frequency characteristics
15 body.

15.1 Use of the transmission mode
15.1 body.

16 Final section
Final body.
""".strip()

    clauses = _split_etsi_clauses(
        text
    )

    numbers = [
        number
        for (
            number,
            _,
            _,
        ) in clauses
    ]

    assert numbers == [
        "1",
        "8.1.6.2",
        "8.1.6.3",
        "14",
        "15",
        "15.1",
        "16",
    ]

    switching = next(
        item
        for item in clauses
        if item[0] == "8.1.6.2"
    )

    assert (
        "15 b10 90 7 15"
        in switching[2]
    )

    assert (
        "Figure 43"
        in switching[2]
    )

    assert (
        "ASw flags"
        in switching[2]
    )

    real_15 = next(
        item
        for item in clauses
        if item[0] == "15"
    )

    assert (
        real_15[1]
        == "Radio frequency characteristics"
    )


def test_etsi_toc_entries_are_not_returned_as_body_clauses():
    text = """
1 Scope ........................................ 1
2 References ................................... 2
3 Terms ........................................ 3
4 General ...................................... 4
5 System ....................................... 5
6 Multiplex .................................... 6
7 Services ..................................... 7
8 Signalling ................................... 8
9 Coding ....................................... 9
10 Transmission ................................ 10

1 Scope
Real scope.

2 References
Real references.
""".strip()

    clauses = _split_etsi_clauses(
        text
    )

    assert len(clauses) == 2

    assert clauses[0][0] == "1"
    assert clauses[0][1] == "Scope"
    assert clauses[0][2] == "Real scope."

    assert clauses[1][0] == "2"
    assert clauses[1][1] == "References"
