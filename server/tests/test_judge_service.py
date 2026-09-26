import unittest

from app.services import judge_service
from app.services.judge_service import judge_code, language_spec


class LanguageSpecTests(unittest.TestCase):
    def test_only_three_languages_are_offered(self):
        self.assertEqual(set(judge_service.LANGUAGE_SPECS), {"python", "javascript", "java"})

    def test_unknown_language_is_rejected(self):
        with self.assertRaises(ValueError):
            language_spec("cpp")


class JudgeShapeTests(unittest.TestCase):
    def test_no_test_cases_reports_instead_of_passing(self):
        result = judge_code("python", "print(1)", [])
        self.assertFalse(result.ok)
        self.assertEqual(result.status, "judge_error")

    def test_unavailable_sandbox_is_not_a_verdict(self):
        def boom(payload):
            raise judge_service.JudgeUnavailable("down")

        original = judge_service._post
        try:
            judge_service._post = boom
            result = judge_code("python", "print(1)", [{"input": "", "expected_output": "1"}])
        finally:
            judge_service._post = original
        # 沙箱坏了必须报 judge_error，绝不能判成 accepted 或 wrong_answer
        self.assertEqual(result.status, "judge_error")
        self.assertFalse(result.ok)

    def test_trailing_whitespace_does_not_fail_a_case(self):
        # 语法检查是第一次调用，真正运行是第二次；用计数器区分，别靠参数猜
        calls = {"n": 0}

        def fake_post(payload):
            calls["n"] += 1
            if calls["n"] == 1:
                return [{"status": "Accepted", "exitStatus": 0, "files": {}, "fileIds": {}}]
            return [
                {
                    "status": "Accepted",
                    "exitStatus": 0,
                    "files": {"stdout": "42  \n\n"},
                    "time": 1000000,
                }
            ]

        original = judge_service._post
        try:
            judge_service._post = fake_post
            result = judge_code("python", "print(42)", [{"input": "", "expected_output": "42"}])
        finally:
            judge_service._post = original
        self.assertEqual(result.status, "accepted")

    def test_compile_error_is_reported_with_output(self):
        original = judge_service._post
        try:
            judge_service._post = lambda payload: [
                {
                    "status": "Nonzero Exit Status",
                    "exitStatus": 1,
                    "files": {"stderr": "SyntaxError: invalid syntax"},
                }
            ]
            result = judge_code("python", "def broken(:", [{"input": "", "expected_output": "1"}])
        finally:
            judge_service._post = original
        self.assertEqual(result.status, "compile_error")
        self.assertIn("SyntaxError", result.compile_output)


class NormalizeTests(unittest.TestCase):
    def test_strips_line_trailing_spaces_and_blank_lines(self):
        self.assertEqual(judge_service._normalize("a  \nb\n\n\n"), "a\nb")

    def test_keeps_inner_spacing(self):
        self.assertEqual(judge_service._normalize("a b\nc"), "a b\nc")


if __name__ == "__main__":
    unittest.main()
