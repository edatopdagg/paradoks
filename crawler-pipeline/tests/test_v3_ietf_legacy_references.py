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



class NumericIetfReferenceTests(
    unittest.TestCase
):

    def test_parses_numeric_normative_rfc_references(
        self,
    ):
        text = """
Normative References

[
1
] Schulzrinne, H. and S. Casner,
"RTP Profile for Audio and Video Conferences",
RFC 3551,
July 2003.

[
2
] Bradner, S.,
"Key Words for Use in RFCs to Indicate Requirement Levels",
BCP 14,
RFC 2119,
March 1997.
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
                "3551",
                "2119",
            ],
        )

        self.assertTrue(
            all(
                reference.reference_kind
                == "normative"
                for reference in references
            )
        )


    def test_accepts_dotted_normative_references_heading(
        self,
    ):
        text = """
. Normative References

[
4
] Rivest, R.,
"The MD5 Message-Digest Algorithm",
RFC 1321,
April 1992.

[
5
] Eastlake, D.,
"Randomness Requirements for Security",
RFC 4086,
June 2005.
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
                "1321",
                "4086",
            },
        )

        self.assertTrue(
            all(
                reference.reference_kind
                == "normative"
                for reference in references
            )
        )


    def test_numeric_non_rfc_entry_does_not_create_ietf_edge(
        self,
    ):
        text = """
Normative References

[
1
] Zahn, L., Dineen, T., and P. Leach,
"Network Computing Architecture",
ISBN 0-13-611674-4,
January 1990.

[
2
] Rivest, R.,
"The MD5 Message-Digest Algorithm",
RFC 1321,
April 1992.
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
                "1321",
            ],
        )




class IetfPageHeaderReferenceTests(
    unittest.TestCase
):

    def test_does_not_treat_page_header_rfc_as_numeric_reference(
        self,
    ):
        text = """
. Normative References

[
8
] National Institute of Standards and Technology,
"Secure Hash Standard",
FIPS PUB 180-1,
April 1995.

Leach, et al. Standards Track [Page 17]
RFC 4122
A UUID URN Namespace July 2005

Appendix A
"""

        references = parse_v3_references(
            "IETF",
            text,
        )

        self.assertEqual(
            references,
            [],
        )


    def test_skips_page_header_but_keeps_next_real_rfc_reference(
        self,
    ):
        text = """
Informative References

[
11
] Schulzrinne, H.,
"Issues in designing a transport protocol for
audio and video conferences"
expired Internet Draft,
October 1993.

Schulzrinne, et al. Standards Track [Page 100]
RFC 3550
RTP July 2003

[
12
] Rosenberg, J.,
"SIP: Session Initiation Protocol",
RFC 3261,
June 2002.
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
                "3261",
            ],
        )

        self.assertEqual(
            references[0].reference_kind,
            "informative",
        )




class IetfReferenceSectionBoundaryTests(
    unittest.TestCase
):

    def test_normative_section_stops_before_appendix(
        self,
    ):
        text = """
. Normative References

[
4
] Rivest, R.,
"The MD5 Message-Digest Algorithm",
RFC 1321,
April 1992.

[
5
] Eastlake, D.,
"Randomness Requirements for Security",
RFC 4086,
June 2005.

Appendix A

some_array[
0
] = nodeid;

/*
See RFC 1750 for historical randomness guidance.
*/
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
                "1321",
                "4086",
            ],
        )

        self.assertNotIn(
            "1750",
            {
                reference.code
                for reference in references
            },
        )




class IetfCompoundBibliographyLabelTests(
    unittest.TestCase
):

    def test_keeps_compound_label_rfc1087_entry_separate(
        self,
    ):
        text = """
. References

[
DDN89
] DCA DDN Defense Communications System,
"DDN Security Bulletin 03",
DDN Security Coordination Center,
17 October 1989.

[Denning, 1990] P. Denning, Editor,
"Computers Under Attack: Intruders, Worms, and Viruses",
ACM Press, 1990.

Fraser, Ed. Informational [Page 67]
RFC 2196
Site Security Handbook September 1997

[IAB-RFC1087, 1989] Internet Activities Board,
"Ethics and the Internet",
RFC 1087,
IAB, January 1989.

[Icove, Seger, and VonStorch, 1995]
D. Icove, K. Seger, and W. VonStorch,
"Computer Crime: A Crimefighter's Handbook",
O'Reilly & Associates, 1995.
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
            references[0].code,
            "1087",
        )

        self.assertEqual(
            references[0].title,
            "Ethics and the Internet",
        )

        self.assertIn(
            "IAB-RFC1087",
            references[0].raw_text,
        )

        self.assertNotIn(
            "DDN Security Bulletin 03",
            references[0].raw_text,
        )


    def test_keeps_compound_label_rfc1135_entry_separate(
        self,
    ):
        text = """
. References

[
OTA-TCT-606
] Congress of the United States,
Office of Technology Assessment,
"Information Security and Privacy in Network Environments",
OTA-TCT-606,
September 1994.

[Palmer and Potter, 1989]
I. Palmer and G. Potter,
"Computer Security Risk Management",
Van Nostrand Reinhold,
1989.

Fraser, Ed. Informational [Page 72]
RFC 2196
Site Security Handbook September 1997

[Reynolds-RFC1135, 1989]
"The Helminthiasis of the Internet",
RFC 1135,
USC/Information Sciences Institute,
December 1989.

[Russell and Gangemi, 1991]
D. Russell and G. Gangemi,
"Computer Security Basics",
O'Reilly & Associates,
1991.
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
            references[0].code,
            "1135",
        )

        self.assertEqual(
            references[0].title,
            "The Helminthiasis of the Internet",
        )

        self.assertIn(
            "Reynolds-RFC1135",
            references[0].raw_text,
        )

        self.assertNotIn(
            (
                "Information Security and Privacy "
                "in Network Environments"
            ),
            references[0].raw_text,
        )


    def test_page_header_does_not_become_entry_when_compound_labels_split(
        self,
    ):
        text = """
. References

[
DDN89
] DCA DDN Defense Communications System,
"DDN Security Bulletin 03",
17 October 1989.

Fraser, Ed. Informational [Page 66]
RFC 2196
Site Security Handbook September 1997

[Eisenberg, et. al., 89]
T. Eisenberg et al.,
"The Computer Worm",
Cornell University,
1989.
"""

        references = parse_v3_references(
            "IETF",
            text,
        )

        self.assertEqual(
            references,
            [],
        )




class IetfUnquotedTitleTests(
    unittest.TestCase
):

    def test_extracts_unquoted_legacy_rfc_title(
        self,
    ):
        text = """
. References

[Reynolds-RFC1135, 1989]
The Helminthiasis of the Internet,
RFC 1135,
USC/Information Sciences Institute,
December 1989.
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
            references[0].code,
            "1135",
        )

        self.assertEqual(
            references[0].title,
            "The Helminthiasis of the Internet",
        )




class IetfGenericAndInformativeReferencesTests(
    unittest.TestCase
):

    def test_keeps_generic_references_when_informative_section_also_exists(
        self,
    ):
        text = """
6
References

[
RFC1700
] Reynolds, J. and J. Postel,
"ASSIGNED NUMBERS",
RFC
1700
, October 1994.

[
RFC2026
] Bradner, S.,
"The Internet Standards Process -- Revision 3",
BCP 9,
RFC 2026,
October 1996.

[
RFC2119
] Bradner, S.,
"Key words for use in RFCs to Indicate Requirement Levels",
BCP 14,
RFC 2119,
March 1997.

[
RFC2960
] Stewart, R. et al.,
"Stream Control Transmission Protocol",
RFC 2960,
October 2000.

7.1
Informative References

[
STONE
] Stone, J.,
"Checksums in the Internet",
Doctoral dissertation,
August 2001.

[
Williams93
] Williams, R.,
"A PAINLESS GUIDE TO CRC ERROR DETECTION ALGORITHMS",
August 1993.
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
                "1700",
                "2026",
                "2119",
                "2960",
            ],
        )

        self.assertTrue(
            all(
                reference.reference_kind
                == "unspecified"
                for reference in references
            )
        )



if __name__ == "__main__":
    unittest.main(
        verbosity=2,
    )
