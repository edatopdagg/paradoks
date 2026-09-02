import unittest

from v3_reference_parser import (
    parse_v3_references,
)


class LegacyIetfReferenceTests(
    unittest.TestCase
):

    def test_parses_hyphenated_rfc_label(
        self,
    ):
        text = """
References

[
RFC-2401
] Kent, S. and R. Atkinson,
"Security Architecture for the Internet Protocol",
RFC 2401,
November 1998.

Changes Since
RFC-1883
"""

        references = parse_v3_references(
            "IETF",
            text,
        )

        self.assertEqual(
            len(references),
            1,
        )

        self.assertEqual(
            references[0].org,
            "IETF",
        )

        self.assertEqual(
            references[0].code,
            "2401",
        )

        self.assertEqual(
            references[0].title,
            (
                "Security Architecture "
                "for the Internet Protocol"
            ),
        )


    def test_parses_symbolic_label_with_rfc_in_body(
        self,
    ):
        text = """
References

[
ICMPv6
] Conta, A. and S. Deering,
"ICMP for the Internet Protocol Version 6 (IPv6)",
RFC 2463,
December 1998.

[
ADDRARCH
] Hinden, R. and S. Deering,
"IP Version 6 Addressing Architecture",
RFC 2373,
July 1998.

Changes Since
RFC-1883
"""

        references = parse_v3_references(
            "IETF",
            text,
        )

        self.assertEqual(
            {
                reference.code
                for reference in references
            },
            {
                "2463",
                "2373",
            },
        )


    def test_generic_references_section_does_not_parse_later_history(
        self,
    ):
        text = """
References

[
RFC-2401
] Kent, S. and R. Atkinson,
"Security Architecture for the Internet Protocol",
RFC 2401,
November 1998.

Changes Since
RFC-1883

01) Replaced reference to RFC-1191
with reference to RFC-1981.
"""

        references = parse_v3_references(
            "IETF",
            text,
        )

        self.assertEqual(
            [
                reference.code
                for reference in references
            ],
            [
                "2401",
            ],
        )


if __name__ == "__main__":
    unittest.main(
        verbosity=2,
    )
