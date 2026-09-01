import unittest

from app.services.prompt_builder import (
    SYSTEM_PROMPT,
    build_system_prompt,
    build_user_prompt,
)


_TR_DIRECT_PHRASE = (
    "do\u011fal T\u00fcrk\u00e7eyle"
)

_TR_SYSTEM_RULE = (
    "Do\u011fal ve teknik "
    "T\u00fcrk\u00e7e kullan."
)


class PromptLanguageTests(
    unittest.TestCase
):
    def test_keeps_turkish_prompt_for_turkish_question(
        self,
    ):
        question = (
            "N1 referans noktas\u0131 "
            "ne i\u015fe yarar?"
        )

        system_prompt = build_system_prompt(
            question
        )

        user_prompt = build_user_prompt(
            question=question,
            chunks=[],
        )

        self.assertEqual(
            system_prompt,
            SYSTEM_PROMPT,
        )

        self.assertIn(
            _TR_DIRECT_PHRASE,
            user_prompt,
        )

    def test_uses_english_prompt_for_english_question(
        self,
    ):
        question = (
            "How are HTTP/2 streams multiplexed?"
        )

        system_prompt = build_system_prompt(
            question
        )

        user_prompt = build_user_prompt(
            question=question,
            chunks=[],
        )

        self.assertIn(
            (
                "Answer entirely in natural, precise "
                "technical English."
            ),
            system_prompt,
        )

        self.assertNotIn(
            _TR_SYSTEM_RULE,
            system_prompt,
        )

        self.assertIn(
            "Answer entirely in English.",
            user_prompt,
        )

        self.assertNotIn(
            _TR_DIRECT_PHRASE,
            user_prompt,
        )

        self.assertIn(
            (
                "There is not enough information "
                "in the provided standards"
            ),
            system_prompt,
        )


if __name__ == "__main__":
    unittest.main(
        verbosity=2
    )
