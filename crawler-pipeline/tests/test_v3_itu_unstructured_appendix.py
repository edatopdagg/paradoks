import unittest

from chunker import build_chunks


class ItuUnstructuredAppendixTests(
    unittest.TestCase
):
    def test_keeps_meaningful_itu_document_without_numbered_sections(
        self,
    ):
        document_text = """
[[PAGE:1]]
INTERNATIONAL TELECOMMUNICATION UNION
ITU-T
I.112
Appendix I
TELECOMMUNICATION
STANDARDIZATION SECTOR
(02/2002)
OF ITU

SERIES I: INTEGRATED SERVICES DIGITAL NETWORK
General structure – Terminology
Vocabulary of terms for ISDNs
Appendix I: General telecommunication terminology and definitions

[[PAGE:2]]
FOREWORD
The International Telecommunication Union (ITU) is the
United Nations specialized agency in the field of
telecommunications.

[[PAGE:3]]
ITU-T Recommendation I.112
Vocabulary of terms for ISDNs
Appendix I
General telecommunication terminology and definitions

A related set of telecommunication terminology and
definitions is provided in American National Standard
T1.523-2001, Telecom Glossary 2000.

T1.523-2001 provides hyperlinked definitions for more
than 8000 telecommunication terms. The definitions are
supplemented with clickable graphics and a hyperlinked
acronym list.

In case of differences or conflicts in the definitions
from the reference cited in this appendix and definitions
in ITU-T Recommendations, the latter definitions apply.

[[PAGE:4]]
SERIES OF ITU-T RECOMMENDATIONS
Series A Organization of the work of ITU-T
Series B Means of expression: definitions, symbols,
classification
Printed in Switzerland
Geneva, 2002
""".strip()

        chunks = build_chunks(
            document_text=document_text,
            doc_org="ITU-T",
            doc_code="I.112",
            version="",
            source_url=(
                "https://www.itu.int/rec/"
                "T-REC-I.112"
            ),
        )

        self.assertGreater(
            len(chunks),
            0,
        )

        combined_text = "\n".join(
            chunk.text
            for chunk in chunks
        )

        normalized_text = " ".join(
            combined_text.split()
        )

        self.assertIn(
            (
                "T1.523-2001 provides "
                "hyperlinked definitions"
            ),
            normalized_text,
        )

        self.assertIn(
            (
                "definitions in ITU-T "
                "Recommendations"
            ),
            normalized_text,
        )


if __name__ == "__main__":
    unittest.main()
