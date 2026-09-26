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


    def test_partial_pass_is_not_accepted(self):
        calls = {"n": 0}

        def fake_post(payload):
            calls["n"] += 1
            if calls["n"] == 1:
                return [{"status": "Accepted", "exitStatus": 0, "files": {}, "fileIds": {}}]
            out = "6" if calls["n"] == 2 else "0"
            return [{"status": "Accepted", "exitStatus": 0,
                     "files": {"stdout": out}, "time": 1000000}]

        original = judge_service._post
        try:
            judge_service._post = fake_post
            result = judge_code(
                "python", "print(1)",
                [{"input": "3", "expected_output": "6"}, {"input": "10", "expected_output": "55"}],
            )
        finally:
            judge_service._post = original
        self.assertEqual(result.status, "wrong_answer")
        self.assertEqual((result.passed, result.total), (1, 2))


class DryRunTests(unittest.TestCase):
    """自测只给运行环境，不比对任何期望输出。"""

    def _fake(self, stdout="42", status="Accepted", exit_status=0, stderr=""):
        calls = {"n": 0}

        def fake_post(payload):
            calls["n"] += 1
            if calls["n"] == 1:
                return [{"status": "Accepted", "exitStatus": 0, "files": {}, "fileIds": {}}]
            return [{"status": status, "exitStatus": exit_status,
                     "files": {"stdout": stdout, "stderr": stderr}, "time": 1000000}]

        return fake_post

    def test_returns_stdout_without_comparing(self):
        original = judge_service._post
        try:
            judge_service._post = self._fake(stdout="hello")
            result = judge_service.dry_run("python", "print('hello')")
        finally:
            judge_service._post = original
        self.assertEqual(result.status, "ok")
        self.assertEqual(result.cases[0].actual, "hello")
        # 没有期望输出可比，passed 必须是 None 而不是 False
        self.assertIsNone(result.cases[0].passed)

    def test_empty_stdin_is_a_valid_run(self):
        original = judge_service._post
        try:
            judge_service._post = self._fake(stdout="5")
            result = judge_service.dry_run("python", "print(5)")
        finally:
            judge_service._post = original
        self.assertEqual(result.status, "ok")
        self.assertEqual(result.cases[0].input_text, "")

    def test_compile_error_surfaces_output(self):
        original = judge_service._post
        try:
            judge_service._post = lambda payload: [
                {"status": "Nonzero Exit Status", "exitStatus": 1,
                 "files": {"stderr": "SyntaxError: bad"}}
            ]
            result = judge_service.dry_run("python", "def broken(:")
        finally:
            judge_service._post = original
        self.assertEqual(result.status, "compile_error")
        self.assertIn("SyntaxError", result.compile_output)

    def test_runtime_error_is_reported(self):
        original = judge_service._post
        try:
            judge_service._post = self._fake(
                status="Nonzero Exit Status", exit_status=1, stderr="boom"
            )
            result = judge_service.dry_run("python", "raise SystemExit(1)")
        finally:
            judge_service._post = original
        self.assertEqual(result.status, "runtime_error")
        self.assertIn("boom", result.cases[0].stderr)

    def test_sandbox_down_is_judge_error(self):
        def boom(payload):
            raise judge_service.JudgeUnavailable("down")

        original = judge_service._post
        try:
            judge_service._post = boom
            result = judge_service.dry_run("python", "print(1)")
        finally:
            judge_service._post = original
        self.assertEqual(result.status, "judge_error")


class NormalizeTests(unittest.TestCase):
    def test_strips_line_trailing_spaces_and_blank_lines(self):
        self.assertEqual(judge_service._normalize("a  \nb\n\n\n"), "a\nb")

    def test_keeps_inner_spacing(self):
        self.assertEqual(judge_service._normalize("a b\nc"), "a b\nc")


if __name__ == "__main__":
    unittest.main()
