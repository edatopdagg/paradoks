from chunker import (
    _is_plausible_generic_clause_title,
    _split_generic_clauses,
)


def test_rejects_pdf_math_artifact_title():
    assert not _is_plausible_generic_clause_title(
        "or 31"
    )
    assert not _is_plausible_generic_clause_title(
        "0"
    )
    assert not _is_plausible_generic_clause_title(
        "7 3"
    )


def test_preserves_real_short_and_normal_titles():
    assert _is_plausible_generic_clause_title(
        "Scope"
    )
    assert _is_plausible_generic_clause_title(
        "Announcement switching"
    )
    assert _is_plausible_generic_clause_title(
        "UE"
    )
    assert _is_plausible_generic_clause_title(
        "IP"
    )


def test_false_clause_is_kept_inside_previous_clause_body():
    text = """
8.1.6.2 Announcement switching
The announcement switching description is encoded in FIG 0/19.
15 or 31
Figure 43: Structure of announcement switching field
ASw flags define the active announcement types.
8.1.6.3 OE Announcement support
The next real clause starts here.
""".strip()

    clauses = _split_generic_clauses(
        text
    )

    numbers = [
        item[0]
        for item in clauses
    ]

    assert numbers == [
        "8.1.6.2",
        "8.1.6.3",
    ]

    first = clauses[0]

    assert (
        first[1]
        == "Announcement switching"
    )

    assert (
        "15 or 31"
        in first[2]
    )

    assert (
        "Figure 43"
        in first[2]
    )
