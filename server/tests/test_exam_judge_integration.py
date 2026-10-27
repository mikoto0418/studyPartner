"""Run against the real go-judge container when RUN_JUDGE_INTEGRATION=1."""
import json
import os
import unittest
from pathlib import Path

from app.services import judge_service

ROOT = Path(__file__).parent
LANGUAGES = {"python": "py", "java": "java", "c": "c", "cpp": "cpp"}


def reference(language, task):
    return (ROOT / f"fixtures/exam_1022/reference.{LANGUAGES[language]}.tmpl").read_text(encoding="utf-8").replace("__TASK__", str(task))


@unittest.skipUnless(os.getenv("RUN_JUDGE_INTEGRATION") == "1", "Requires real go-judge")
class JudgeIntegrationTests(unittest.TestCase):
    def test_all_four_languages_pass_all_cases(self):
        data = json.loads((ROOT.parent / "app/data/exam_1022.json").read_text(encoding="utf-8"))
        for language in LANGUAGES:
            for task, question in enumerate(data["questions"], 1):
                with self.subTest(language=language, task=task):
                    result = judge_service.judge_code(language, reference(language, task), question["test_cases"])
                    self.assertTrue(result.ok, f"{language} Q{task}: {result}")
                    self.assertEqual(result.passed, len(question["test_cases"]))

    def test_compile_runtime_timeout_and_wrong_output(self):
        invalid = {
            "python": "def broken(:", "java": "public class Main { broken }",
            "c": "int main( {", "cpp": "int main( {",
        }
        runtime = {
            "python": "raise RuntimeError('test')",
            "java": "public class Main { public static void main(String[] x){throw new RuntimeException();}}",
            "c": "int main(){return 2;}", "cpp": "int main(){return 2;}",
        }
        infinite = {
            "python": "while True: pass",
            "java": "public class Main { public static void main(String[] x){while(true){}}}",
            "c": "int main(){while(1){}}", "cpp": "int main(){while(true){}}",
        }
        for language in LANGUAGES:
            with self.subTest(language=language):
                self.assertEqual(judge_service.dry_run(language, invalid[language]).status, "compile_error")
                self.assertEqual(judge_service.dry_run(language, runtime[language]).status, "runtime_error")
                self.assertEqual(judge_service.dry_run(language, infinite[language]).status, "time_limit")
                result = judge_service.judge_code(language, reference(language, 5), [{"input": "1\n5\n", "expected_output": "B\n"}])
                self.assertEqual(result.status, "wrong_answer")
