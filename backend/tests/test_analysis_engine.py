import sys
import unittest
from pathlib import Path


SERVICES_DIR = Path(__file__).resolve().parents[1] / "services"
sys.path.insert(0, str(SERVICES_DIR))

from analysis_engine import analyze_comment


class SentimentAnalysisTests(unittest.TestCase):
    def test_clear_explanation_is_positive_with_original_evidence(self):
        result = analyze_comment("The teacher explains every topic clearly.")
        self.assertEqual(result["sentiment"], "positive")
        self.assertEqual(result["aspects"][0]["aspect"], "Teaching clarity")
        self.assertEqual(result["aspects"][0]["sentiment"], "positive")
        self.assertEqual(result["aspects"][0]["evidence"], "The teacher explains every topic clearly.")

    def test_mixed_knowledge_and_unclear_explanations_stays_mixed_negative(self):
        result = analyze_comment("The teacher is knowledgeable but does not explain concepts properly.")
        aspects = {item["aspect"]: item for item in result["aspects"]}
        self.assertEqual(result["sentiment"], "negative")
        self.assertTrue(result["mixed_opinion"])
        self.assertEqual(aspects["Subject knowledge"]["sentiment"], "positive")
        self.assertEqual(aspects["Teaching clarity"]["sentiment"], "negative")

    def test_practical_learning_and_teaching_pace(self):
        practical = analyze_comment("Practical sessions are very useful.")
        pace = analyze_comment("I cannot understand the teaching speed.")
        self.assertEqual(practical["aspects"][0]["aspect"], "Practical learning")
        self.assertEqual(practical["aspects"][0]["sentiment"], "positive")
        self.assertEqual(pace["sentiment"], "negative")
        self.assertIn("Teaching pace", {item["aspect"] for item in pace["aspects"]})

    def test_good_explanation_and_difficult_assignments_are_separate(self):
        result = analyze_comment("The teacher explains well, but assignments are too difficult.")
        aspects = {item["aspect"]: item for item in result["aspects"]}
        self.assertTrue(result["mixed_opinion"])
        self.assertEqual(aspects["Teaching clarity"]["sentiment"], "positive")
        self.assertEqual(aspects["Assignments and assessment"]["sentiment"], "negative")

    def test_requested_clarity_and_practical_examples_split(self):
        result = analyze_comment("The teacher explains concepts clearly, but does not give enough practical examples.")
        aspects = {item["aspect"]: item for item in result["aspects"]}
        self.assertEqual(result["sentiment"], "negative")
        self.assertTrue(result["mixed_opinion"])
        self.assertEqual(aspects["Teaching clarity"]["sentiment"], "positive")
        self.assertEqual(aspects["Practical learning"]["sentiment"], "negative")

    def test_hindi_and_telugu_example_phrases_are_supported(self):
        hindi = analyze_comment("शिक्षक बहुत अच्छी तरह समझाते हैं।")
        telugu = analyze_comment("చాలా బాగా బోధిస్తారు.")
        self.assertEqual((hindi["language"], hindi["sentiment"], hindi["language_supported"]), ("Hindi", "positive", True))
        self.assertEqual((telugu["language"], telugu["sentiment"], telugu["language_supported"]), ("Telugu", "positive", True))

    def test_unrecognized_language_is_not_misreported_as_a_real_neutral_result(self):
        result = analyze_comment("教師授課很好。")
        self.assertEqual(result["sentiment"], "neutral")
        self.assertFalse(result["language_supported"])
        self.assertEqual(result["analysis_method"], "language_guard")
        self.assertIn("placeholder", result["analysis_note"])

    def test_negated_positive_word_is_negative(self):
        result = analyze_comment("I cannot understand the explanation.")
        self.assertEqual(result["sentiment"], "negative")


if __name__ == "__main__":
    unittest.main()
