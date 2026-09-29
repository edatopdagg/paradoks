import sys
from pathlib import Path


ROOT = (
    Path(__file__)
    .resolve()
    .parents[1]
)

sys.path.insert(
    0,
    str(
        ROOT / "src"
    ),
)

from chunker import (
    split_into_clauses,
)


def test_etsi_figure_bit_label_does_not_split_real_clause():

    text = """8.1.6.2 Announcement switching
The announcement switching description is encoded in FIG 0/19.
15 or 31
Figure 43: Structure of announcement switching field
The following definitions apply:
At the start of an announcement, FIG 0/19 shall be signalled
with a repetition rate of ten times per second for five seconds.
Then it shall be signalled once per second.
At the end it shall be signalled ten times per second for two seconds.
8.1.6.3 OE Announcement support
Next real clause.
"""

    clauses = split_into_clauses(
        document_text=text,
        doc_org="ETSI",
    )

    numbers = [
        item[0]
        for item in clauses
    ]

    assert "15" not in numbers

    assert "8.1.6.2" in numbers
    assert "8.1.6.3" in numbers

    target = next(
        item
        for item in clauses
        if item[0] == "8.1.6.2"
    )

    body = target[2]

    assert "Figure 43" in body
    assert "ten times per second" in body
    assert "once per second" in body
    assert "two seconds" in body
