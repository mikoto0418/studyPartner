import unittest
from io import BytesIO

from pypdf import PdfReader

from app.services.score_sheet import render_score_sheet_pdf, summarize_saved_scores


class SummarizeSavedScoresTests(unittest.TestCase):
    def test_ungraded_subjective_is_not_counted_as_zero(self):
        summary = summarize_saved_scores(
            "pending_review",
            [("single", 8, True), ("essay", 0, False)],
        )
        self.assertEqual(summary["objective_score"], 8)
        self.assertIsNone(summary["subjective_score"])
        self.assertIsNone(summary["total_score"])
        self.assertTrue(summary["pending"])

    def test_saved_subjective_score_is_included(self):
        summary = summarize_saved_scores(
            "submitted",
            [("single", 8, True), ("short", 6.5, True)],
        )
        self.assertEqual(summary["objective_score"], 8)
        self.assertEqual(summary["subjective_score"], 6.5)
        self.assertEqual(summary["total_score"], 14.5)
        self.assertFalse(summary["pending"])

    def test_in_progress_has_no_scores(self):
        summary = summarize_saved_scores("in_progress", [("single", 5, True)])
        self.assertEqual(
            summary,
            {
                "objective_score": None,
                "subjective_score": None,
                "total_score": None,
                "pending": False,
            },
        )

    def test_objective_only_paper_leaves_subjective_blank(self):
        summary = summarize_saved_scores("submitted", [("judge", 2, True), ("fill", 0, True)])
        self.assertEqual(summary["objective_score"], 2)
        self.assertIsNone(summary["subjective_score"])
        self.assertEqual(summary["total_score"], 2)


    def test_a_saved_zero_is_kept(self):
        summary = summarize_saved_scores("submitted", [("essay", 0, True)])
        self.assertEqual(summary["subjective_score"], 0)
        self.assertEqual(summary["total_score"], 0)
        self.assertFalse(summary["pending"])


class ScoreSheetPdfTests(unittest.TestCase):
    def test_pdf_leaves_ungraded_subjective_blank(self):
        pdf = render_score_sheet_pdf(
            {
                "title": "期中测验",
                "rows": [
                    {
                        "student_name": "张三",
                        "username": "stu01",
                        "status": "pending_review",
                        "objective_score": 8,
                        "subjective_score": None,
                        "total_score": None,
                        "pending": True,
                    }
                ],
            }
        )
        text = PdfReader(BytesIO(pdf)).pages[0].extract_text()
        self.assertIn("张三", text)
        self.assertIn("待批改", text)
        self.assertIn("8 — — 是", text)
        self.assertNotIn("8 0", text)


if __name__ == "__main__":
    unittest.main()
