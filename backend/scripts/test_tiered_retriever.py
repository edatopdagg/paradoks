from __future__ import annotations

import unittest

from app.services.tiered_retriever import (
    TieredRetriever,
)


class TieredRetrieverSignalTests(
    unittest.TestCase
):

    def test_document_signals_keep_acronyms(
        self,
    ) -> None:

        signals = (
            TieredRetriever._document_signals(
                {
                    "org": "NRSC",
                    "code": "NRSC-4-B",
                    "title": (
                        "United States RBDS Standard - "
                        "Specification of the Radio "
                        "Broadcast Data System (RBDS)"
                    ),
                }
            )
        )

        self.assertIn(
            "rbds",
            signals,
        )

        self.assertIn(
            "nrsc-4-b",
            signals,
        )


    def test_document_signals_keep_dvb_code(
        self,
    ) -> None:

        signals = (
            TieredRetriever._document_signals(
                {
                    "org": "ETSI",
                    "code": "EN 302 755",
                    "title": (
                        "Digital Video Broadcasting (DVB); "
                        "second generation terrestrial "
                        "television broadcasting system "
                        "(DVB-T2)"
                    ),
                }
            )
        )

        self.assertIn(
            "dvb-t2",
            signals,
        )

        self.assertIn(
            "302",
            signals,
        )


    def test_normal_words_do_not_become_signals(
        self,
    ) -> None:

        signals = (
            TieredRetriever._document_signals(
                {
                    "org": "TEST",
                    "code": "DOC 1",
                    "title": (
                        "Implementation guidelines "
                        "for broadcasting system"
                    ),
                }
            )
        )

        self.assertNotIn(
            "implementation",
            signals,
        )

        self.assertNotIn(
            "guidelines",
            signals,
        )


if __name__ == "__main__":

    unittest.main(
        verbosity=2
    )
