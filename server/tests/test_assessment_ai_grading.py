import unittest

from app.services.assessment_service import AssessmentService


parse_grade_response = getattr(AssessmentService, "_parse_ai_grade_response", None)


class ParseAiGradeResponseTests(unittest.TestCase):
    def test_parses_score_and_comment(self):
        self.assertTrue(callable(parse_grade_response), "AI grade response parser must exist")
        self.assertEqual(
            parse_grade_response('{"score": 7.5, "comment": "包含主要要点"}', 10),
            (7.5, "包含主要要点"),
        )

    def test_clamps_score_to_question_range(self):
        self.assertTrue(callable(parse_grade_response), "AI grade response parser must exist")
        self.assertEqual(
            parse_grade_response('{"score": 99, "comment": "超出范围"}', 10),
            (10.0, "超出范围"),
        )

    def test_rejects_invalid_json_instead_of_silently_suggesting_zero(self):
        self.assertTrue(callable(parse_grade_response), "AI grade response parser must exist")
        with self.assertRaisesRegex(ValueError, "有效 JSON"):
            parse_grade_response("上游截断了输出", 10)

    def test_rejects_missing_or_non_numeric_score(self):
        self.assertTrue(callable(parse_grade_response), "AI grade response parser must exist")
        for content in ('{"comment":"没有分数"}', '{"score":"很多"}'):
            with self.subTest(content=content):
                with self.assertRaisesRegex(ValueError, "有效分数"):
                    parse_grade_response(content, 10)

    def test_rejects_nan_score(self):
        self.assertTrue(callable(parse_grade_response), "AI grade response parser must exist")
        with self.assertRaisesRegex(ValueError, "有效分数"):
            parse_grade_response('{"score": NaN}', 10)


if __name__ == "__main__":
    unittest.main()
