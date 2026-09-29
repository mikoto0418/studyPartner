"""边界场景排查：限时收卷、重复进入、越权、状态机。

与 e2e_smoke.py 的分工：那个走正常主流程，这个专挑容易出错的边缘路径。
"""
import asyncio
import json
import os
import sys
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timedelta, timezone

BASE = os.environ.get("E2E_BASE", "http://127.0.0.1:8001/api/v1")
CLASS_ID = os.environ.get("E2E_CLASS_ID", "2bd0817c-6345-40ce-8322-8e76afb56cbc")

results = []


def check(name, ok, detail=""):
    results.append((name, ok, detail))
    print(("PASS  " if ok else "FAIL  ") + name + (f"  <- {detail}" if detail and not ok else ""))


def call(method, path, token=None, body=None, timeout=180):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", "Bearer " + token)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        text = e.read().decode("utf-8", "replace")
        try:
            return e.code, json.loads(text)
        except json.JSONDecodeError:
            return e.code, {"raw": text}


def login(username, password):
    _, d = call("POST", "/auth/login", body={"username": username, "password": password})
    return d["data"]["access_token"]


async def attempt_status(attempt_id):
    """读一份作答的当前状态，用来判断是不是「别人已经先收过卷了」。"""
    from app.core.database import SessionLocal
    from app.models.assessment import AssessmentAttempt
    from sqlalchemy import select

    async with SessionLocal() as db:
        row = (await db.execute(
            select(AssessmentAttempt).where(AssessmentAttempt.id == uuid.UUID(attempt_id))
        )).scalars().first()
        return row.status if row else None


async def seed(title, questions, **paper_kwargs):
    from app.core.database import SessionLocal
    from app.models.assessment import AssessmentPaper, AssessmentQuestion
    from app.models.user import User
    from sqlalchemy import select

    async with SessionLocal() as db:
        teacher = (await db.execute(select(User).where(User.username == "teacher"))).scalars().first()
        paper = AssessmentPaper(
            creator_id=teacher.id, title=title, parse_status="awaiting_review",
            question_count=len(questions), **paper_kwargs,
        )
        db.add(paper)
        await db.flush()
        for i, q in enumerate(questions):
            db.add(AssessmentQuestion(paper_id=paper.id, order_index=i, **q))
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
        for a in (await db.execute(
            select(AssessmentAttempt).where(AssessmentAttempt.paper_id == paper.id)
        )).scalars().all():
            await db.execute(delete(BehaviorEvent).where(BehaviorEvent.attempt_id == a.id))
            await db.execute(delete(AssessmentAnswer).where(AssessmentAnswer.attempt_id == a.id))
            await db.delete(a)
        await db.execute(delete(AssessmentAssignment).where(AssessmentAssignment.paper_id == paper.id))
        await db.execute(delete(AssessmentQuestion).where(AssessmentQuestion.paper_id == paper.id))
        await db.delete(paper)
        await db.commit()


async def run_all():
    teacher = login("teacher", "teacher123")
    student = login("student", "student123")
    _, me = call("GET", "/auth/me", student)
    student_id = me["data"]["id"]

    # ---------- 1. 未设分值的题不允许发布 ----------
    pid = await seed("边界-未设分值", [
        {"question_type": "single", "stem": "1+1?", "options": [{"key": "A", "text": "2"}],
         "answer": "A", "score": 2},
        {"question_type": "single", "stem": "2+2?", "options": [{"key": "A", "text": "4"}],
         "answer": "A", "score": None},
    ])
    try:
        status, d = call("POST", f"/assessment/papers/{pid}/publish", teacher,
                         {"publish_target": {"type": "class", "ids": [CLASS_ID]}})
        check("有题未设分值时拒绝发布", status >= 400 and "分值" in str(d.get("message", "")), str(d)[:150])
    finally:
        await cleanup(pid)

    # ---------- 2. 限时到点自动收卷 ----------
    pid = await seed("边界-限时收卷", [
        {"question_type": "single", "stem": "1+1?", "options": [{"key": "A", "text": "2"}],
         "answer": "A", "score": 2},
    ])
    try:
        status, d = call("POST", f"/assessment/papers/{pid}/publish", teacher, {
            "publish_target": {"type": "class", "ids": [CLASS_ID]},
            "time_limit_minutes": 30,
        })
        check("限时发布成功", status == 200, str(d)[:120])

        _, att = call("POST", f"/assessment/student/papers/{pid}/attempts", student)
        attempt_id = att["data"]["id"]
        _, dl = call("GET", f"/assessment/papers/{pid}/questions", teacher)
        qid = dl["data"][0]["id"]
        call("PUT", f"/assessment/student/attempts/{attempt_id}/answers", student,
             {"answers": [{"question_id": qid, "answer": "A"}]})

        # 把 started_at 拨回到 40 分钟前，等价于限时已过
        from app.core.database import SessionLocal
        from app.models.assessment import AssessmentAttempt
        from sqlalchemy import select
        async with SessionLocal() as db:
            row = (await db.execute(
                select(AssessmentAttempt).where(AssessmentAttempt.id == uuid.UUID(attempt_id))
            )).scalars().first()
            row.started_at = datetime.now(timezone.utc) - timedelta(minutes=40)
            await db.commit()

        # 本地开了 inline 调度器时，它可能已经先收过卷了；这时本次调用返回 0 也算正常，
        # 真正要保证的是「最终确实被收卷」，而不是「必须是这一次调用动的手」。
        before_status = await attempt_status(attempt_id)
        from app.services.assessment_service import AssessmentService
        async with SessionLocal() as db:
            finalized = await AssessmentService.finalize_expired_attempts(db)
        check("限时过期被到点任务收卷",
              finalized >= 1 or before_status != "in_progress",
              f"finalized={finalized} before={before_status}")

        _, after = call("GET", f"/assessment/papers/{pid}/attempts", teacher)
        row = next((a for a in after["data"] if a["id"] == attempt_id), None)
        check("收卷后状态为已交卷或待批改",
              bool(row and row["status"] in ("submitted", "pending_review")), str(row)[:150])
        check("收卷后按已存答案判分", bool(row and row["score"] == 2.0), f"score={row and row['score']}")
    finally:
        await cleanup(pid)

    # ---------- 3. 截止时间到点自动收卷 ----------
    pid = await seed("边界-截止收卷", [
        {"question_type": "judge", "stem": "地球是圆的", "answer": "true", "score": 1},
    ])
    try:
        # 先用未来的截止时间发布（过去的话根本开不了考，那是第 4 条覆盖的场景）
        call("POST", f"/assessment/papers/{pid}/publish", teacher, {
            "publish_target": {"type": "class", "ids": [CLASS_ID]},
            "due_at": (datetime.now(timezone.utc) + timedelta(minutes=30)).isoformat(),
        })
        _, att = call("POST", f"/assessment/student/papers/{pid}/attempts", student)
        check("未来截止时间的试卷可以开考", att.get("data") is not None, str(att)[:120])
        attempt_id = att["data"]["id"]

        # 把截止时间拨到过去，模拟时间流逝
        from app.core.database import SessionLocal
        from app.models.assessment import AssessmentPaper
        from app.services.assessment_service import AssessmentService
        from sqlalchemy import select
        async with SessionLocal() as db:
            row = (await db.execute(
                select(AssessmentPaper).where(AssessmentPaper.id == uuid.UUID(pid))
            )).scalars().first()
            target = dict(row.publish_target or {})
            target["due_at"] = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
            row.publish_target = target
            await db.commit()
        before_status = await attempt_status(attempt_id)
        async with SessionLocal() as db:
            finalized = await AssessmentService.finalize_expired_attempts(db)
        check("截止时间过期被到点任务收卷",
              finalized >= 1 or before_status != "in_progress",
              f"finalized={finalized} before={before_status}")
    finally:
        await cleanup(pid)

    # ---------- 4. 过期后不能再开考 ----------
    pid = await seed("边界-过期不给开考", [
        {"question_type": "single", "stem": "x", "options": [{"key": "A", "text": "a"}],
         "answer": "A", "score": 1},
    ])
    try:
        call("POST", f"/assessment/papers/{pid}/publish", teacher, {
            "publish_target": {"type": "class", "ids": [CLASS_ID]},
            "due_at": (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat(),
        })
        status, d = call("POST", f"/assessment/student/papers/{pid}/attempts", student)
        check("过期试卷拒绝开始作答", status >= 400, f"status={status} {str(d)[:120]}")
    finally:
        await cleanup(pid)

    # ---------- 5. 重复进入只产生一份作答 ----------
    pid = await seed("边界-重复进入", [
        {"question_type": "single", "stem": "x", "options": [{"key": "A", "text": "a"}],
         "answer": "A", "score": 1},
    ])
    try:
        call("POST", f"/assessment/papers/{pid}/publish", teacher,
             {"publish_target": {"type": "class", "ids": [CLASS_ID]}})
        ids = []
        for _ in range(4):
            _, r = call("POST", f"/assessment/student/papers/{pid}/attempts", student)
            ids.append(r["data"]["id"])
        check("多次进入复用同一份作答", len(set(ids)) == 1, str(set(ids)))
    finally:
        await cleanup(pid)

    # ---------- 6. 交卷后不能再保存草稿 / 重复交卷 ----------
    pid = await seed("边界-交卷后状态", [
        {"question_type": "single", "stem": "x", "options": [{"key": "A", "text": "a"}],
         "answer": "A", "score": 1},
    ])
    try:
        call("POST", f"/assessment/papers/{pid}/publish", teacher,
             {"publish_target": {"type": "class", "ids": [CLASS_ID]}})
        _, q = call("GET", f"/assessment/student/papers/{pid}/questions", student)
        qid = q["data"][0]["id"]
        _, att = call("POST", f"/assessment/student/papers/{pid}/attempts", student)
        attempt_id = att["data"]["id"]
        call("POST", f"/assessment/student/attempts/{attempt_id}/submit", student,
             {"answers": [{"question_id": qid, "answer": "A"}]})

        s1, d1 = call("PUT", f"/assessment/student/attempts/{attempt_id}/answers", student,
                      {"answers": [{"question_id": qid, "answer": "A"}]})
        check("交卷后拒绝保存草稿", s1 >= 400, f"status={s1} {str(d1)[:100]}")

        s2, d2 = call("POST", f"/assessment/student/attempts/{attempt_id}/submit", student,
                      {"answers": [{"question_id": qid, "answer": "A"}]})
        check("交卷后拒绝重复交卷", s2 >= 400, f"status={s2} {str(d2)[:100]}")

        s3, d3 = call("POST",
                      f"/assessment/student/attempts/{attempt_id}/questions/{qid}/run",
                      student, {"code": "print(1)"})
        check("交卷后拒绝自测", s3 >= 400, f"status={s3} {str(d3)[:100]}")
    finally:
        await cleanup(pid)

    # ---------- 7. 越权 ----------
    pid = await seed("边界-越权", [
        {"question_type": "single", "stem": "x", "options": [{"key": "A", "text": "a"}],
         "answer": "A", "score": 1},
    ])
    try:
        call("POST", f"/assessment/papers/{pid}/publish", teacher, {
            "publish_target": {"type": "student", "ids": [student_id]},
        })
        # 另一名不存在的学生 id 不能看到
        s, _ = call("GET", f"/assessment/student/papers/{pid}/questions",
                    student)
        check("发布给自己的试卷可以取题", s == 200, f"status={s}")

        s2, d2 = call("POST", f"/assessment/papers/{pid}/publish", student,
                      {"publish_target": {"type": "class", "ids": [CLASS_ID]}})
        check("学生无权发布试卷", s2 in (401, 403), f"status={s2}")

        s3, _ = call("GET", f"/assessment/papers/{pid}/attempts", student)
        check("学生无权看监考数据", s3 in (401, 403), f"status={s3}")
    finally:
        await cleanup(pid)

    # ---------- 8. 指定学生发布：范围外的人取不到题 ----------
    pid = await seed("边界-范围外", [
        {"question_type": "single", "stem": "x", "options": [{"key": "A", "text": "a"}],
         "answer": "A", "score": 1},
    ])
    try:
        # 发给一个随机的（不存在的）学生
        call("POST", f"/assessment/papers/{pid}/publish", teacher, {
            "publish_target": {"type": "student", "ids": [str(uuid.uuid4())]},
        })
        s, d = call("GET", f"/assessment/student/papers/{pid}/questions", student)
        check("发布给他人时本学生取不到题", s >= 400, f"status={s} {str(d)[:120]}")
    finally:
        await cleanup(pid)


def main():
    asyncio.run(run_all())
    failed = [r for r in results if not r[1]]
    print(f"\n=== {len(results) - len(failed)}/{len(results)} 通过 ===")
    for name, _, detail in failed:
        print("  FAIL", name, detail)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
