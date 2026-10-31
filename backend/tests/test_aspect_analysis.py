import unittest
import sys
import os
from pathlib import Path

# Add backend directory to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from services.aspect_analysis import analyze, review_summary, teacher_improvement_suggestions


class AspectAnalysisTests(unittest.TestCase):
    def test_7_user_positive_cases(self):
        cases = [
            ("The practical sessions are excellent.", "positive", "Practical learning"),
            ("The faculty are approachable and always willing to clarify doubts.", "positive", "Doubt clarification"),
            ("The curriculum is well structured and relevant to industry requirements.", "positive", "Course organization"),
            ("The college provides wonderful opportunities for students through workshops, seminars, internships, and technical events.", "positive", "Career opportunities"),
            ("The faculty members genuinely care about students' academic growth.", "positive", "Academic support"),
            ("The teachers always encourage us to think creatively, ask questions, and explore beyond the syllabus.", "positive", "Student engagement"),
            ("The practical sessions are excellent. They provide hands-on experience and help us gain confidence in applying theoretical concepts.", "positive", "Practical learning"),
        ]
        for text, exp_sentiment, exp_aspect in cases:
            with self.subTest(text=text):
                res = analyze(text)
                self.assertEqual(res["sentiment"], exp_sentiment)
                matched_aspects = [a["aspect"] for a in res["aspects"]]
                self.assertIn(exp_aspect, matched_aspects)
                # Confirm no negative complaint tasks generated for purely positive feedback
                for s in res["improvement_suggestions"]:
                    self.assertNotIn("choose one teaching change", s)
                    self.assertNotIn("what needs to be changed", s)

    def test_diverse_38_feedback_suite(self):
        suite = [
            ("The professor explains difficult concepts with crystal clear clarity.", "positive", "Teaching clarity"),
            ("Dr. Rao has exceptional subject knowledge and makes lectures inspiring.", "positive", "Subject knowledge"),
            ("The classroom atmosphere is very friendly, respectful, and motivating.", "positive", "Learning environment"),
            ("Lab computers and campus Wi-Fi infrastructure are top notch.", "positive", "Infrastructure"),
            ("The syllabus was completed well on time with well organized lecture notes.", "positive", "Course organization"),
            ("The interactive discussions keep everyone attentive and excited to learn.", "positive", "Student engagement"),
            ("Mentorship provided by our department has helped me secure an internship.", "positive", "Academic support"),
            ("The lab experiments gave me valuable practical skills.", "positive", "Practical learning"),
            ("The campus recruitment drives offer outstanding career options.", "positive", "Career opportunities"),
            ("All topics are modern and highly relevant to industry standards.", "positive", "Industry relevance"),
            ("The teacher patiently answers every single student question.", "positive", "Doubt clarification"),
            ("Overall teaching quality across all modules is commendable.", "positive", "Teaching effectiveness"),

            ("The teacher goes way too fast and I cannot understand the explanations.", "negative", "Teaching clarity"),
            ("Faculty is unapproachable and never clarifies student doubts.", "negative", "Doubt clarification"),
            ("The curriculum is outdated and completely irrelevant to industry needs.", "negative", "Industry relevance"),
            ("Lab equipment is broken and the computers frequently crash.", "negative", "Infrastructure"),
            ("The lectures are very boring, dull, and monotonous.", "negative", "Student engagement"),
            ("There are no campus placement drives or internship opportunities provided.", "negative", "Career opportunities"),
            ("The professor lacks subject knowledge and gives confusing answers.", "negative", "Subject knowledge"),
            ("Assignments are excessively difficult and grading is unfair.", "negative", "Course organization"),

            ("Lectures are held from 9 AM to 4 PM every weekday.", "neutral", None),
            ("The textbook prescribed for this course is Database Systems by Silberschatz.", "neutral", None),
            ("We submitted the project report on the online student portal yesterday.", "neutral", None),
            ("The syllabus has five modules and two mid-term examinations.", "neutral", "Course organization"),
            ("The lab is located on the second floor of the engineering block.", "neutral", "Practical learning"),
            ("Attendance is recorded at the beginning of each class.", "neutral", None),

            ("The teacher is very knowledgeable, but does not explain concepts clearly.", "mixed", "Subject knowledge"),
            ("Practical lab sessions are great, but the computers are outdated.", "mixed", "Practical learning"),
            ("The curriculum is relevant, but the pace is too rushed.", "mixed", "Course organization"),
            ("The faculty is friendly and approachable, but rarely available after class hours.", "mixed", "Doubt clarification"),
            ("Course materials are well organized, but assignments are overly demanding.", "mixed", "Course organization"),
            ("I enjoy the interactive discussions, although some topics feel rushed.", "mixed", "Student engagement"),

            ("शिक्षक बहुत अच्छी तरह समझाते हैं।", "positive", None),
            ("చాలా బాగా బోధిస్తారు.", "positive", None),
            ("शिक्षक का तरीका बिल्कुल समझ नहीं आया।", "negative", None),
            ("బోధన అస్సలు అర్థం కాలేదు.", "negative", None),
        ]
        for text, exp_sentiment, exp_aspect in suite:
            with self.subTest(text=text):
                res = analyze(text)
                self.assertEqual(res["sentiment"], exp_sentiment, f"Failed sentiment on '{text}'")
                if exp_aspect:
                    matched = [a["aspect"] for a in res["aspects"]]
                    self.assertIn(exp_aspect, matched, f"Failed aspect '{exp_aspect}' on '{text}'")


if __name__ == "__main__":
    unittest.main()
