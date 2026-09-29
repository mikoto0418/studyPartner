"""端到端冒烟：教师发题 → 学生作答 → 判题 → 批改 → 导出，逐项断言。

用真实 HTTP 打后端，不走浏览器，目的是把「接口契约」层面的回归一次性跑出来。
"""
import asyncio
import io
import json
import os
import sys
import urllib.error
import urllib.request
import uuid

BASE = os.environ.get("E2E_BASE", "http://127.0.0.1:8001/api/v1")
CLASS_ID = os.environ.get("E2E_CLASS_ID", "2bd0817c-6345-40ce-8322-8e76afb56cbc")

results = []


def check(name, ok, detail=""):
    results.append((name, ok, detail))
    print(("PASS  " if ok else "FAIL  ") + name + (f"  <- {detail}" if detail and not ok else ""))


def call(method, path, token=None, body=None, raw=False, timeout=180):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", "Bearer " + token)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = resp.read()
            if raw:
                return resp.status, payload, dict(resp.headers)
            return resp.status, json.loads(payload.decode()), dict(resp.headers)
    except urllib.error.HTTPError as e:
        body_text = e.read().decode("utf-8", "replace")
        try:
            return e.code, json.loads(body_text), dict(e.headers)
        except json.JSONDecodeError:
            return e.code, {"raw": body_text}, dict(e.headers)


def login(username, password):
    _, d, _ = call("POST", "/auth/login", body={"username": username, "password": password})
    data = d["data"]
    return data["access_token"], data["user"]["id"]


async def seed_paper():
    """直接落库造一份覆盖四种题型的试卷，避开上传/拆题的外部依赖。"""
    from sqlalchemy import select
    from app.core.database import SessionLocal
    from app.models.assessment import AssessmentPaper, AssessmentQuestion
    from app.models.user import User

    async with SessionLocal() as db:
        teacher = (await db.execute(select(User).where(User.username == "teacher"))).scalars().first()
        paper = AssessmentPaper(
            creator_id=teacher.id, title="端到端冒烟卷", parse_status="awaiting_review",
            question_count=4,
        )
        db.add(paper)
        await db.flush()
        db.add(AssessmentQuestion(paper_id=paper.id, order_index=0, question_type="single",
            stem="下列哪个是 Python 的列表推导式？",
            options=[{"key": "A", "text": "[x for x in range(3)]"}, {"key": "B", "text": "{x: 1}"}],
            answer="A", score=2))
        db.add(AssessmentQuestion(paper_id=paper.id, order_index=1, question_type="judge",
            stem="Python 的 GIL 使多线程无法利用多核。", answer="true", score=2))
        db.add(AssessmentQuestion(paper_id=paper.id, order_index=2, question_type="code",
            stem="读入一个整数 n，输出 1 到 n 的和。", language="python",
            starter_code="n = int(input())\n",
            test_cases=[{"input": "3", "expected_output": "6"},
                        {"input": "10", "expected_output": "55"}],
            answer="print(sum(range(1, int(input()) + 1)))", score=10))
        db.add(AssessmentQuestion(paper_id=paper.id, order_index=3, question_type="essay",
            stem="简述进程与线程的区别。", answer="进程是资源分配单位，线程是调度单位。", score=6))
        await db.commit()
        return str(paper.id)


async def cleanup(paper_id):
    from sqlalchemy import select, delete
    from app.core.database import SessionLocal
    from app.models.assessment import (AssessmentPaper, AssessmentQuestion,
        AssessmentAttempt, AssessmentAnswer, AssessmentAssignment, BehaviorEvent)
    async with SessionLocal() as db:
        paper = (await db.execute(
            select(AssessmentPaper).where(AssessmentPaper.id == uuid.UUID(paper_id))
        )).scalars().first()
        if not paper:
            return
        attempts = (await db.execute(
            select(AssessmentAttempt).where(AssessmentAttempt.paper_id == paper.id)
        )).scalars().all()
        for a in attempts:
            await db.execute(delete(BehaviorEvent).where(BehaviorEvent.attempt_id == a.id))
            await db.execute(delete(AssessmentAnswer).where(AssessmentAnswer.attempt_id == a.id))
            await db.delete(a)
        await db.execute(delete(AssessmentAssignment).where(AssessmentAssignment.paper_id == paper.id))
        await db.execute(delete(AssessmentQuestion).where(AssessmentQuestion.paper_id == paper.id))
        await db.delete(paper)
        await db.commit()


async def main_async():
    """整个流程跑在同一个事件循环里。

    分成两次 asyncio.run 会让 SQLAlchemy 的连接池绑在已关闭的循环上，
    第二次建连直接抛 'NoneType' object has no attribute 'send'。
    """
    paper_id = await seed_paper()
    try:
        run_checks(paper_id)
    finally:
        await cleanup(paper_id)


def main():
    asyncio.run(main_async())
    failed = [r for r in results if not r[1]]
    print(f"\n=== {len(results) - len(failed)}/{len(results)} 通过 ===")
    for name, _, detail in failed:
        print("  FAIL", name, detail)
    return 1 if failed else 0


def run_checks(paper_id):
    teacher, _teacher_uid = login("teacher", "teacher123")
    student, student_uid = login("student", "student123")
    check("教师登录", bool(teacher))
    check("学生登录", bool(student))

    # ---- 发布：全屏关闭 ----
    status, d, _ = call("POST", f"/assessment/papers/{paper_id}/publish", teacher, {
        "publish_target": {"type": "class", "ids": [CLASS_ID]},
        "require_fullscreen": False,
    })
    check("发布成功", status == 200 and d.get("code") == 0, f"status={status} body={d}")
    target = (d.get("data") or {}).get("publish_target") or {}
    check("发布后 require_fullscreen=False 落库", target.get("require_fullscreen") is False, str(target))

    # ---- 学生取题：不能泄露用例 ----
    status, d, _ = call("GET", f"/assessment/student/papers/{paper_id}/questions", student)
    questions = d.get("data") or []
    check("学生取题成功", status == 200 and len(questions) == 4, f"status={status} n={len(questions)}")
    leaked = [q for q in questions if "test_cases" in q or "sample_cases" in q]
    check("题目接口不泄露测试用例", not leaked, str(leaked)[:200])
    code_q = next((q for q in questions if q["question_type"] == "code"), None)
    check("编程题带 language 与起始代码", bool(code_q and code_q.get("language") == "python"
          and code_q.get("starter_code")), str(code_q)[:200])
    check("试卷列表回传 require_fullscreen=False",
          any(p.get("require_fullscreen") is False
              for p in (call("GET", "/assessment/student/papers", student)[1].get("data") or [])
              if str(p.get("id")) == paper_id))

    # ---- 开始作答 ----
    status, d, _ = call("POST", f"/assessment/student/papers/{paper_id}/attempts", student)
    attempt_id = (d.get("data") or {}).get("id")
    check("开始作答", status == 200 and bool(attempt_id), f"status={status} body={d}")

    # ---- 草稿保存 ----
    q_by_type = {q["question_type"]: q["id"] for q in questions}
    status, d, _ = call("PUT", f"/assessment/student/attempts/{attempt_id}/answers", student, {
        "answers": [{"question_id": q_by_type["single"], "answer": "A"}]
    })
    check("草稿保存", status == 200 and d.get("code") == 0, f"status={status} body={d}")

    # ---- 自测：不比对期望输出，只回标准输出 ----
    status, d, _ = call("POST",
        f"/assessment/student/attempts/{attempt_id}/questions/{q_by_type['code']}/run",
        student, {"code": "print(2 + 3)"})
    run_data = d.get("data") or {}
    check("自测（无输入）", status == 200 and run_data.get("status") == "ok", f"status={status} body={d}")
    case = (run_data.get("cases") or [{}])[0]
    check("自测回标准输出", case.get("actual_output", "").strip() == "5", str(case)[:200])
    check("自测不返回期望输出", "expected_output" not in case, str(case)[:200])
    status, d, _ = call("POST",
        f"/assessment/student/attempts/{attempt_id}/questions/{q_by_type['code']}/run",
        student, {"code": "n = int(input())\nprint(n * 2)", "stdin": "21"})
    run_data = d.get("data") or {}
    case = (run_data.get("cases") or [{}])[0]
    check("自测（带输入）", run_data.get("status") == "ok"
          and case.get("actual_output", "").strip() == "42", str(run_data)[:200])
    check("自测返回剩余次数", isinstance(run_data.get("runs_left"), int), str(run_data.get("runs_left")))

    status, d, _ = call("POST",
        f"/assessment/student/attempts/{attempt_id}/questions/{q_by_type['code']}/run",
        student, {"code": "def broken(:"})
    check("自测语法错误报编译错误", (d.get("data") or {}).get("status") == "compile_error",
          str(d.get("data"))[:200])

    status, d, _ = call("POST",
        f"/assessment/student/attempts/{attempt_id}/questions/{q_by_type['single']}/run",
        student, {"code": "print(1)"})
    check("非编程题拒绝自测", status >= 400, f"status={status}")

    # ---- 交卷：编程题全用例通过自动满分 ----
    status, d, _ = call("POST", f"/assessment/student/attempts/{attempt_id}/submit", student, {
        "answers": [
            {"question_id": q_by_type["single"], "answer": "A"},
            {"question_id": q_by_type["judge"], "answer": "对"},
            {"question_id": q_by_type["code"],
             "answer": "n = int(input())\nprint(sum(range(1, n + 1)))"},
            {"question_id": q_by_type["essay"], "answer": "进程是资源分配单位，线程是调度单位。"},
        ]
    })
    submitted = d.get("data") or {}
    check("交卷成功", status == 200 and submitted.get("status") in ("submitted", "pending_review"),
          f"status={status} body={d}")
    check("含主观题时状态为待批改", submitted.get("status") == "pending_review", str(submitted))
    check("客观题 + 编程题已计入得分", submitted.get("score") == 14.0, f"score={submitted.get('score')}")

    # ---- 教师批改视图 ----
    status, d, _ = call("GET", f"/assessment/attempts/{attempt_id}/answers", teacher)
    answers = d.get("data") or []
    code_ans = next((a for a in answers if a["question_type"] == "code"), None)
    check("教师可见编程题判题汇总", bool(code_ans and code_ans.get("judge_summary")
          and code_ans["judge_summary"].get("passed") == 2), str(code_ans)[:300] if code_ans else "none")
    check("教师可见逐用例明细", bool(code_ans and (code_ans.get("judge_detail") or {}).get("cases")),
          str(code_ans)[:200] if code_ans else "none")
    check("判题已自动给满分并置已批改",
          bool(code_ans and code_ans.get("graded") and code_ans.get("score") == 10.0),
          str(code_ans)[:200] if code_ans else "none")

    # ---- 主观题批改 ----
    essay_id = q_by_type["essay"]
    status, d, _ = call("POST", f"/assessment/attempts/{attempt_id}/grade", teacher, {
        "grades": [{"question_id": essay_id, "score": 5}]
    })
    check("主观题批改成功", status == 200, f"status={status} body={d}")
    graded = d.get("data") or {}
    check("批改后转已交卷", graded.get("status") == "submitted", str(graded))
    check("总分重算正确", graded.get("score") == 19.0, f"score={graded.get('score')}")

    # ---- 学生成绩回顾 ----
    status, d, _ = call("GET", f"/assessment/student/papers/{paper_id}/review", student)
    review = d.get("data") or {}
    check("成绩回顾可取", status == 200 and bool(review.get("questions")), f"status={status}")
    review_code = next((q for q in review.get("questions", []) if q["question_type"] == "code"), None)
    check("回顾只给通过数不给用例内容",
          bool(review_code and review_code.get("judge_summary")
               and "test_cases" not in review_code and "sample_cases" not in review_code),
          str(review_code)[:250] if review_code else "none")

    # ---- 监考中心 ----
    status, d, _ = call("GET", f"/assessment/papers/{paper_id}/attempts", teacher)
    check("监考列表可取", status == 200 and len(d.get("data") or []) == 1, f"status={status}")

    status, d, _ = call("GET", f"/assessment/attempts/{attempt_id}/insights", teacher)
    insights = d.get("data") or {}
    check("按题画像可取", status == 200 and len(insights.get("questions") or []) == 4,
          f"status={status}")

    status, d, _ = call("GET", f"/assessment/attempts/{attempt_id}/behavior", teacher)
    check("行为事件可取", status == 200, f"status={status}")

    # ---- 成绩单 PDF ----
    status, payload, headers = call("GET", f"/assessment/papers/{paper_id}/score-sheet.pdf",
                                    teacher, raw=True)
    check("成绩单导出成功", status == 200 and payload[:4] == b"%PDF", f"status={status}")
    check("成绩单文件名是 PDF",
          "pdf" in (headers.get("content-disposition") or headers.get("Content-Disposition") or ""),
          str(headers.get("content-disposition"))[:120])

    # ---- 试卷分析 / 班级看板 / 历次考试 ----
    status, d, _ = call("GET", f"/assessment/papers/{paper_id}/analytics", teacher)
    check("试卷分析可取", status == 200, f"status={status}")

    status, d, _ = call("GET", f"/assessment/classes/{CLASS_ID}/exam-analytics", teacher)
    check("班级考试概况可取", status == 200, f"status={status}")

    status, d, _ = call("GET", "/assessment/papers", teacher)
    check("教师试卷列表可取", status == 200, f"status={status}")

    # ---- 越权：学生不能看别人的批改接口 ----
    status, d, _ = call("GET", f"/assessment/attempts/{attempt_id}/answers", student)
    check("学生无权访问教师批改接口", status in (401, 403), f"status={status}")

    # ---- 全屏配置：默认值 ----
    status, d, _ = call("POST", f"/assessment/papers/{paper_id}/publish", teacher, {
        "publish_target": {"type": "class", "ids": [CLASS_ID]},
    })
    if status == 200:
        target = (d.get("data") or {}).get("publish_target") or {}
        check("不传 require_fullscreen 时默认 true", target.get("require_fullscreen") is True,
              str(target))
    else:
        # 已发布后不可再发布是合法状态，不算失败
        check("已发布试卷拒绝重复发布", status >= 400, f"status={status}")

    # ---- 限时落库 ----
    status, d, _ = call("POST", f"/assessment/papers/{paper_id}/publish", teacher, {
        "publish_target": {"type": "class", "ids": [CLASS_ID]},
        "time_limit_minutes": 90,
    })
    if status == 200:
        target = (d.get("data") or {}).get("publish_target") or {}
        check("限时落库", target.get("time_limit_minutes") == 90, str(target))

    # ---- 班级看板：某学生历次考试 ----
    status, d, _ = call("GET", f"/assessment/classes/{CLASS_ID}/students/"
                              f"{student_uid}/exams", teacher)
    history = d.get("data") or {}
    check("历次考试接口可取", status == 200 and "attempts" in history, f"status={status}")
    if status == 200:
        row = next((a for a in history.get("attempts", []) if a.get("paper_id") == paper_id), None)
        check("历次考试含本次作答且带分数",
              bool(row and row.get("status") == "submitted" and row.get("score") == 19.0),
              str(row)[:250] if row else "not found")

    # ---- 成绩单：待批改时主观分留空 ----
    # 另造一份只有编程题、未批的作答来验证留空逻辑
    check_score_sheet_blank(teacher, student)


def check_score_sheet_blank(teacher, student):
    """待批改状态下成绩单不能把没批的主观题写成 0 分。"""
    from app.services.score_sheet import summarize_saved_scores

    pending = summarize_saved_scores(
        "pending_review",
        [("single", 2.0, True), ("essay", 0.0, False)],
    )
    check("待批改时主观分留空", pending["subjective_score"] is None, str(pending))
    check("待批改时总分留空", pending["total_score"] is None, str(pending))
    check("待批改时客观分照常统计", pending["objective_score"] == 2.0, str(pending))
    check("待批改标记为真", pending["pending"] is True, str(pending))

    done = summarize_saved_scores(
        "submitted",
        [("single", 2.0, True), ("essay", 5.0, True)],
    )
    check("批完后总分 = 客观 + 主观", done["total_score"] == 7.0, str(done))


if __name__ == "__main__":
    sys.exit(main())
