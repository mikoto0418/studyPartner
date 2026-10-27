"""Real API smoke test; run only against a disposable *_test database."""
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import httpx
from sqlalchemy.engine import make_url

from app.config import settings
from app.interview_1022 import CLASS_ID
from app.main import app
from app.core.database import engine

BASE = Path(__file__).resolve().parent
DATA = json.loads((BASE.parent / "app/data/exam_1022.json").read_text(encoding="utf-8"))


async def main():
    if not make_url(settings.async_database_uri).database.endswith("_test"):
        raise ValueError("Only a disposable *_test database is allowed")
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test", timeout=180) as client:
        async def call(method, path, headers=None, data=None):
            response = await client.request(method, "/api/v1" + path, headers=headers, json=data)
            assert response.status_code == 200, (path, response.status_code, response.text[:500])
            return response.json()["data"]
        async def login(username):
            result = await call("POST", "/auth/login", data={"username": username, "password": username})
            return {"Authorization": "Bearer " + result["access_token"]}

        teacher = await login("tea10221")
        # 正式卷维持草稿，创建另一个测试卷走真实命题 API。
        paper = await call("POST", "/assessment/papers", teacher, {"title": "1022编译验收（测试库）"})
        print("API_TEST_PAPER_ID=" + paper["id"], flush=True)
        assert paper["source_file_id"] is None and paper["parse_status"] == "awaiting_review"
        await call("PUT", f"/assessment/papers/{paper['id']}/questions", teacher, {"questions": DATA["questions"]})
        questions = await call("GET", f"/assessment/papers/{paper['id']}/questions", teacher)
        await call("POST", f"/assessment/papers/{paper['id']}/publish", teacher, {
            "publish_target": {"type": "class", "ids": [str(CLASS_ID)]},
            "require_fullscreen": False,
        })
        for index, (language, suffix) in enumerate((("python", "py"), ("java", "java"), ("c", "c"), ("cpp", "cpp")), 1):
            student = await login(f"stu1022{index:02d}")
            await call("POST", "/auth/identity", student, {"name": f"编译验收{language}"})
            attempt = await call("POST", f"/assessment/student/papers/{paper['id']}/attempts", student)
            public = await call("GET", f"/assessment/student/papers/{paper['id']}/questions", student)
            assert all("test_cases" not in q and "analysis" not in q and "answer" not in q for q in public)
            template = (BASE / f"fixtures/exam_1022/reference.{suffix}.tmpl").read_text(encoding="utf-8")
            answers = []
            for task, q in enumerate(questions, 1):
                code = template.replace("__TASK__", str(task))
                result = await call("POST", f"/assessment/student/attempts/{attempt['id']}/questions/{q['id']}/run",
                                    student, {"code": code, "stdin": DATA["questions"][task-1]["test_cases"][0]["input"], "language": language})
                assert result["status"] == "ok", (language, task, result)
                expected = DATA["questions"][task-1]["test_cases"][0]["expected_output"].strip()
                assert result["cases"][0]["actual_output"].strip() == expected
                answers.append({"question_id": q["id"], "answer": {"language": language, "code": code}})
            await call("PUT", f"/assessment/student/attempts/{attempt['id']}/answers", student, {"answers": answers})
            saved = await call("GET", f"/assessment/student/papers/{paper['id']}/answers", student)
            assert all(row["answer"]["language"] == language for row in saved["answers"])
            submitted = await call("POST", f"/assessment/student/attempts/{attempt['id']}/submit", student, {"answers": answers})
            assert submitted["score"] == 140 and submitted["status"] == "submitted", (language, submitted)
            print(f"PASS {language}: manual authoring -> sample runs -> save/restore language -> submit 140 points", flush=True)
        for username in ("tea10222", "tea10223"):
            other = await login(username)
            stats = await call("GET", f"/assessment/papers/{paper['id']}/attempts", other)
            assert len(stats) == 4
        print("PASS shared teachers can monitor all 4 results; hidden data stays private", flush=True)
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
