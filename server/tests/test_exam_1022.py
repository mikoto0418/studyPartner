import json
import unittest
from pathlib import Path
from types import SimpleNamespace
from app.core.exceptions import ValidationError
from app.services.assessment_service import AssessmentService
from app.services.question_parser import normalize_code_language


class ExamDataTests(unittest.TestCase):
    def test_data_is_complete_and_multi_language(self):
        data = json.loads((Path(__file__).parents[1] / "app/data/exam_1022.json").read_text(encoding="utf-8"))
        self.assertEqual(data["title"], "1022二面")
        self.assertEqual([q["score"] for q in data["questions"]], [20, 20, 20, 40, 40])
        for question in data["questions"]:
            self.assertEqual(question["language"], "multi")
            self.assertIn("样例", question["stem"])
            self.assertGreaterEqual(len(question["test_cases"]), 12)

    def test_revised_inputs_follow_confirmed_ranges(self):
        data = json.loads((Path(__file__).parents[1] / "app/data/exam_1022.json").read_text(encoding="utf-8"))
        dates, colors, cipher, delivery, candy = data["questions"]
        for case in colors['test_cases']:
            n, *endpoints = map(int, case['input'].split())
            self.assertTrue(1 <= n < 1000000)
            self.assertEqual(len(endpoints), 6)
            self.assertTrue(all(1 <= endpoints[i] <= endpoints[i+1] <= n for i in (0, 2, 4)))
            output = list(map(int, case['expected_output'].split()))
            self.assertEqual(len(output), 7)
            self.assertEqual(sum(output), n)
            self.assertTrue(all(v >= 0 for v in output))
        self.assertEqual(max(len(c['input'].strip()) for c in cipher['test_cases']), 999999)
        for case in cipher['test_cases']:
            text = case['input'].strip()
            self.assertTrue(1 <= len(text) < 1000000 and text.isascii() and text.isalpha())
            expected = ''.join(c.upper() if 'a' <= c <= 'z' else chr((ord(c)-65+1)%26+65) for c in text)
            self.assertEqual(expected, case['expected_output'].strip())
        for case in dates["test_cases"]:
            start, end = map(int, case["input"].split())
            self.assertTrue(20000101 <= start <= end <= 20261022)
        for case in delivery["test_cases"]:
            lines = case["input"].strip().splitlines()
            n = int(lines[0])
            self.assertTrue(1 <= n <= 1000)
            self.assertEqual(len(lines), n + 1)
            for line in lines[1:]:
                floor, room = map(int, line.split())
                self.assertTrue(1 <= floor <= 6)
                self.assertEqual(room // 100, floor)
                self.assertTrue(1 <= room % 100 <= 40)
        for case in candy["test_cases"]:
            n, *values = map(int, case["input"].split())
            self.assertTrue(1 <= n <= 20)
            self.assertEqual(len(values), n)
            self.assertTrue(all(1 <= value < 1000 for value in values))
        self.assertEqual(
            {case["expected_output"].strip() for case in candy["test_cases"]},
            {"A", "B", "F"},
        )

    def test_selected_language_is_validated_and_code_remains_plain_text(self):
        q = SimpleNamespace(language="multi")
        for language in ("python", "java", "c", "cpp"):
            answer = {"language": language, "code": "print(1)"}
            self.assertEqual(AssessmentService._code_language(q, answer), language)
            self.assertEqual(AssessmentService._answer_text(answer), "print(1)")
        for language in (None, "javascript", "ruby", "/bin/sh"):
            with self.assertRaises(ValidationError):
                AssessmentService._code_language(q, requested=language)
        with self.assertRaises(ValidationError):
            AssessmentService._code_language(SimpleNamespace(language="python"), requested="cpp")
        self.assertEqual(normalize_code_language("C++"), "cpp")
        self.assertEqual(normalize_code_language("multi"), "multi")
