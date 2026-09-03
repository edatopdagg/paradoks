import unittest
from unittest.mock import patch

import resolver
from models import DocStatus, Reference


class ItuRevisionFamilyFallbackTests(
    unittest.TestCase
):
    def _reference(
        self,
        *,
        code,
        title,
        raw_text,
    ):
        return Reference(
            org="ITU-T",
            code=code,
            title=title,
            raw_text=raw_text,
        )

    def test_generic_reference_prefers_base_over_newer_corrigendum(
        self,
    ):
        landing_url = (
            "https://www.itu.int/rec/"
            "T-REC-G.810/en"
        )

        base_link = (
            "./recommendation.asp?"
            "lang=en&"
            "parent=T-REC-G.810-199608-I"
        )

        cor_link = (
            "./recommendation.asp?"
            "lang=en&"
            "parent=T-REC-G.810-200111-I!Cor1"
        )

        base_url = (
            "https://www.itu.int/rec/"
            "T-REC-G.810/"
            "recommendation.asp?"
            "lang=en&"
            "parent=T-REC-G.810-199608-I"
        )

        pdf_link = (
            "/rec/dologin_pub.asp?"
            "lang=e&"
            "id=T-REC-G.810-199608-I!!PDF-E&"
            "type=items"
        )

        landing_response = object()
        base_response = object()

        responses = {
            landing_url: landing_response,
            base_url: base_response,
        }

        response_links = {
            id(landing_response): [
                base_link,
                cor_link,
            ],
            id(base_response): [
                pdf_link,
            ],
        }

        with patch.object(
            resolver,
            "_get",
            side_effect=lambda url: (
                responses.get(url)
            ),
        ), patch.object(
            resolver,
            "_links",
            side_effect=lambda response: (
                response_links.get(
                    id(response),
                    [],
                )
            ),
        ):
            result = resolver._resolve_itu(
                self._reference(
                    code="G.810",
                    title=(
                        "Definitions and terminology "
                        "for synchronization networks"
                    ),
                    raw_text=(
                        "ITU-T Recommendation G.810"
                    ),
                )
            )

        self.assertEqual(
            result.status,
            DocStatus.PENDING,
        )

        self.assertIn(
            "G.810-199608-I!!PDF-E",
            result.source_url,
        )

        self.assertNotIn(
            "Cor1",
            result.source_url,
        )

    def test_generic_reference_prefers_base_over_newer_amendment(
        self,
    ):
        landing_url = (
            "https://www.itu.int/rec/"
            "T-REC-G.8261/en"
        )

        base_link = (
            "./recommendation.asp?"
            "lang=en&"
            "parent=T-REC-G.8261-201908-I"
        )

        amd_link = (
            "./recommendation.asp?"
            "lang=en&"
            "parent=T-REC-G.8261-202010-I!Amd2"
        )

        base_url = (
            "https://www.itu.int/rec/"
            "T-REC-G.8261/"
            "recommendation.asp?"
            "lang=en&"
            "parent=T-REC-G.8261-201908-I"
        )

        pdf_link = (
            "/rec/dologin_pub.asp?"
            "lang=e&"
            "id=T-REC-G.8261-201908-I!!PDF-E&"
            "type=items"
        )

        landing_response = object()
        base_response = object()

        responses = {
            landing_url: landing_response,
            base_url: base_response,
        }

        response_links = {
            id(landing_response): [
                base_link,
                amd_link,
            ],
            id(base_response): [
                pdf_link,
            ],
        }

        with patch.object(
            resolver,
            "_get",
            side_effect=lambda url: (
                responses.get(url)
            ),
        ), patch.object(
            resolver,
            "_links",
            side_effect=lambda response: (
                response_links.get(
                    id(response),
                    [],
                )
            ),
        ):
            result = resolver._resolve_itu(
                self._reference(
                    code="G.8261",
                    title=(
                        "Timing and Synchronization "
                        "aspects in Packet networks"
                    ),
                    raw_text=(
                        "ITU-T Recommendation G.8261"
                    ),
                )
            )

        self.assertEqual(
            result.status,
            DocStatus.PENDING,
        )

        self.assertIn(
            "G.8261-201908-I!!PDF-E",
            result.source_url,
        )

        self.assertNotIn(
            "Amd2",
            result.source_url,
        )

    def test_i112_semantic_identity_keeps_appendix_one(
        self,
    ):
        landing_url = (
            "https://www.itu.int/rec/"
            "T-REC-I.112/en"
        )

        base_link = (
            "./recommendation.asp?"
            "lang=en&"
            "parent=T-REC-I.112-199303-I"
        )

        app_link = (
            "./recommendation.asp?"
            "lang=en&"
            "parent=T-REC-I.112-200202-I!App1"
        )

        app_url = (
            "https://www.itu.int/rec/"
            "T-REC-I.112/"
            "recommendation.asp?"
            "lang=en&"
            "parent=T-REC-I.112-200202-I!App1"
        )

        pdf_link = (
            "/rec/dologin_pub.asp?"
            "lang=e&"
            "id=T-REC-I.112-200202-I!App1!PDF-E&"
            "type=items"
        )

        landing_response = object()
        app_response = object()

        responses = {
            landing_url: landing_response,
            app_url: app_response,
        }

        response_links = {
            id(landing_response): [
                base_link,
                app_link,
            ],
            id(app_response): [
                pdf_link,
            ],
        }

        with patch.object(
            resolver,
            "_get",
            side_effect=lambda url: (
                responses.get(url)
            ),
        ), patch.object(
            resolver,
            "_links",
            side_effect=lambda response: (
                response_links.get(
                    id(response),
                    [],
                )
            ),
        ):
            result = resolver._resolve_itu(
                self._reference(
                    code="I.112",
                    title=(
                        "General telecommunication "
                        "terminology and definitions"
                    ),
                    raw_text=(
                        "ITU-T Recommendation I.112"
                    ),
                )
            )

        self.assertEqual(
            result.status,
            DocStatus.PENDING,
        )

        self.assertIn(
            "I.112-200202-I!App1!PDF-E",
            result.source_url,
        )


if __name__ == "__main__":
    unittest.main()
