import unittest

from v3_reference_parser import (
    parse_v3_references,
)


class IetfReferenceParserTests(unittest.TestCase):
    def test_parses_multiline_rfc_references(self) -> None:
        text = """
Normative References
[
RFC2119
] Bradner, S., "Key words for use in RFCs",
RFC 2119, March 1997.

Informative References
[
FALL96
] Fall, K., "Simulation-based Comparisons",
July 1996.

[
RFC4086
] Eastlake, D., "Randomness Requirements",
RFC 4086, June 2005.
"""

        references = parse_v3_references(
            org="IETF",
            document_text=text,
        )

        self.assertEqual(
            [reference.code for reference in references],
            ["2119", "4086"],
        )

        self.assertEqual(
            references[0].reference_kind,
            "normative",
        )

        self.assertEqual(
            references[1].reference_kind,
            "informative",
        )

    def test_prefers_normative_duplicate(self) -> None:
        text = """
Normative References
[
RFC2119
] First occurrence.

Informative References
[
RFC2119
] Duplicate occurrence.
"""

        references = parse_v3_references(
            org="IETF",
            document_text=text,
        )

        self.assertEqual(
            len(references),
            1,
        )

        self.assertEqual(
            references[0].reference_kind,
            "normative",
        )


class EtsiReferenceParserTests(unittest.TestCase):
    def test_normalizes_3gpp_etsi_aliases(self) -> None:
        text = """
[1] ETSI TS 123 041: Cell Broadcast Service.
[2] ETSI TS 122 268: Public Warning System.
[3] ETSI TS 102 182: Emergency Communications.
"""

        references = parse_v3_references(
            org="ETSI",
            document_text=text,
        )

        self.assertEqual(
            references[0].org,
            "3GPP",
        )
        self.assertEqual(
            references[0].code,
            "TS 23.041",
        )

        self.assertEqual(
            references[1].org,
            "3GPP",
        )
        self.assertEqual(
            references[1].code,
            "TS 22.268",
        )

        self.assertEqual(
            references[2].org,
            "ETSI",
        )
        self.assertEqual(
            references[2].code,
            "TS 102 182",
        )


class ThreeGppReferenceParserTests(unittest.TestCase):
    def test_keeps_standard_3gpp_reference(self) -> None:
        text = """
[1] 3GPP TS 23.040: Technical realization of SMS.
"""

        references = parse_v3_references(
            org="3GPP",
            document_text=text,
        )

        self.assertEqual(
            len(references),
            1,
        )
        self.assertEqual(
            references[0].org,
            "3GPP",
        )
        self.assertEqual(
            references[0].code,
            "TS 23.040",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)