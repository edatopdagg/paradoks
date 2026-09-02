import unittest

from chunker import build_chunks


class IetfSplitHeadingWithoutTocTests(
    unittest.TestCase
):

    def test_parses_split_section_headings_without_toc(
        self,
    ):
        document_text = """
Network Working Group R. Glenn
Request for Comments: 2410
Category: Standards Track
November 1998

The NULL Encryption Algorithm and Its Use With IPsec

Status of this Memo

This document specifies an Internet standards track protocol.

1
. Introduction

This memo defines the NULL encryption algorithm and its use
with the IPsec Encapsulating Security Payload.

2
. Algorithm Definition

NULL is defined mathematically by the Identity function.

2.1
Keying Material

The NULL encryption algorithm can make use of keys of
varying lengths.

2.2
Cryptographic Synchronization

It is not necessary to transmit an IV.

3
. ESP_NULL Operational Requirements

ESP_NULL is defined by using NULL within the context of ESP.

4
. Security Considerations

The NULL encryption algorithm offers no confidentiality.

5
. Intellectual Property Rights

The authors represent that they have disclosed relevant
intellectual property rights.

6
. Acknowledgments

Steve Bellovin suggested text for this document.

7
. References

[RFC2119] Bradner, S.,
"Key words for use in RFCs to Indicate Requirement Levels",
RFC 2119, March 1997.
"""

        chunks = build_chunks(
            document_text=document_text,
            doc_org="IETF",
            doc_code="2410",
            version="RFC 2410",
            source_url=(
                "https://www.rfc-editor.org/"
                "rfc/rfc2410.html"
            ),
        )

        self.assertGreater(
            len(chunks),
            0,
        )

        clauses = {
            chunk.clause
            for chunk in chunks
        }

        self.assertTrue(
            {
                "1",
                "2",
                "2.1",
                "2.2",
                "3",
                "4",
                "5",
                "6",
                "7",
            }.issubset(
                clauses
            )
        )

        introduction_chunks = [
            chunk
            for chunk in chunks
            if chunk.clause == "1"
        ]

        self.assertTrue(
            introduction_chunks
        )

        self.assertTrue(
            any(
                "NULL encryption algorithm"
                in chunk.text
                for chunk
                in introduction_chunks
            )
        )


    def test_does_not_reopen_sections_from_late_page_numbers(
        self,
    ):
        from chunker import (
            _split_ietf_clauses,
        )

        document_text = """
Network Working Group
Request for Comments: 2410

1
. Introduction

Introduction body.

2
. Algorithm Definition

Algorithm body.

6
. Acknowledgments

Acknowledgments body.

7
. References

[RFC2119] Bradner, S.,
"Key words for use in RFCs to Indicate Requirement Levels",
RFC 2119, March 1997.

6
. Editors' Addresses

Rob Glenn
NIST
EMail: rob.glenn@example.com

7
. Full Copyright Statement

Copyright (C) The Internet Society.
"""

        clauses = _split_ietf_clauses(
            document_text
        )

        clause_numbers = [
            clause_number
            for (
                clause_number,
                _title,
                _body,
            ) in clauses
        ]

        self.assertEqual(
            clause_numbers,
            [
                "1",
                "2",
                "6",
                "7",
            ],
        )

        titles = [
            title
            for (
                _clause_number,
                title,
                _body,
            ) in clauses
        ]

        self.assertNotIn(
            "Editors' Addresses",
            titles,
        )

        self.assertNotIn(
            "Full Copyright Statement",
            titles,
        )


if __name__ == "__main__":
    unittest.main(
        verbosity=2,
    )
