import unittest

from app.services.question_planner import (
    build_question_plan,
    detect_language,
)


class LanguageDetectionTests(unittest.TestCase):
    def test_detects_turkish_question(self) -> None:
        self.assertEqual(
            detect_language(
                "N1 üzerinden hangi sinyalleşme taşınır?"
            ),
            "tr",
        )

    def test_detects_english_question(self) -> None:
        self.assertEqual(
            detect_language(
                "Which signalling is carried over N1?"
            ),
            "en",
        )


class QuestionPlanningTests(unittest.TestCase):
    def test_keeps_single_question_as_one_item(self) -> None:
        plan = build_question_plan(
            "N1 referans noktası nedir?"
        )

        self.assertEqual(plan.language, "tr")
        self.assertEqual(len(plan.questions), 1)

    def test_splits_two_turkish_questions(self) -> None:
        plan = build_question_plan(
            "N1 üzerinden hangi sinyalleşme taşınır "
            "ve bu sinyalleşme neden NAS olarak adlandırılır?"
        )

        self.assertEqual(plan.language, "tr")
        self.assertEqual(len(plan.questions), 2)
        self.assertIn(
            "hangi sinyalleşme",
            plan.questions[0].text.casefold(),
        )
        self.assertIn(
            "neden nas",
            plan.questions[1].text.casefold(),
        )

    def test_splits_two_english_questions(self) -> None:
        plan = build_question_plan(
            "Which protocol does HTTP/3 use "
            "and why was that protocol chosen?"
        )

        self.assertEqual(plan.language, "en")
        self.assertEqual(len(plan.questions), 2)
        self.assertIn(
            "which protocol",
            plan.questions[0].text.casefold(),
        )
        self.assertIn(
            "why",
            plan.questions[1].text.casefold(),
        )

    def test_classifies_purpose_question(self) -> None:
        plan = build_question_plan(
            "N3 referans noktasının 5G mimarisindeki görevi nedir?"
        )

        self.assertEqual(
            plan.questions[0].intent,
            "purpose",
        )

    def test_classifies_exact_identity_question(self) -> None:
        plan = build_question_plan(
            "UE ile AMF arasındaki referans noktası hangisidir?"
        )

        self.assertEqual(
            plan.questions[0].intent,
            "identity",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)