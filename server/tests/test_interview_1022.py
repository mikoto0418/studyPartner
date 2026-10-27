"""Integration tests against an explicitly supplied, disposable PostgreSQL test DB."""
import asyncio
import os
import unittest
from unittest.mock import patch
from uuid import uuid4

import bcrypt
import httpx
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.database import get_db
from app.core.exceptions import NotFoundError
from app.core.security import verify_password
from app.interview_1022 import CLASS_ID, STUDENTS, TEACHERS, account_id, seed_interview
from app.main import app
from app.models import Base
from app.models.assessment import AssessmentPaper
from app.models.learning_path import ClassGroup, ClassMember, ClassTeacher
from app.models.user import User
from app.services.access_control import AccessControlService
from app.services.assessment_service import AssessmentService
from app.services.learning_path_service import LearningPathService
from app.services.user_service import UserService

TEST_URL = os.getenv("INTERVIEW_TEST_DATABASE_URL", "")


@unittest.skipUnless(TEST_URL, "Set INTERVIEW_TEST_DATABASE_URL to a disposable *_test PostgreSQL DB")
class InterviewTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        from sqlalchemy.engine import make_url
        if not (make_url(TEST_URL).database or "").endswith("_test"):
            raise ValueError("Refusing to reset a database whose name does not end in _test")
        self.engine = create_async_engine(TEST_URL)
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)
        self.hash_patch = patch(
            "app.interview_1022.get_password_hash",
            side_effect=lambda value: bcrypt.hashpw(value.encode(), bcrypt.gensalt(rounds=4)).decode(),
        )
        self.hash_patch.start()
        async with self.sessions.begin() as db:
            await seed_interview(db)

        async def override_db():
            async with self.sessions() as db:
                yield db
        app.dependency_overrides[get_db] = override_db
        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")

    async def asyncTearDown(self):
        await self.client.aclose()
        app.dependency_overrides.clear()
        self.hash_patch.stop()
        await self.engine.dispose()

    async def login(self, username):
        result = await self.client.post("/api/v1/auth/login", json={"username": username, "password": username})
        self.assertEqual(result.status_code, 200, result.text)
        return {"Authorization": f"Bearer {result.json()['data']['access_token']}"}

    async def test_seed_counts_passwords_and_rerun_preserves_identity(self):
        async with self.sessions() as db:
            for username in TEACHERS + STUDENTS:
                user = await UserService.get_user_by_username(db, username)
                self.assertTrue(verify_password(username, user.password_hash), username)
            student = await UserService.get_user_by_username(db, STUDENTS[0])
            await UserService.confirm_identity(db, student, "张三")
            student.password_hash = "changed-password-hash"
            await db.commit()
            async with db.begin():
                self.assertEqual(await seed_interview(db), 0)
            self.assertEqual((await db.execute(select(func.count(User.id)))).scalar(), 43)
            self.assertEqual((await db.execute(select(func.count(ClassMember.id)))).scalar(), 40)
            self.assertEqual((await db.execute(select(func.count()).select_from(ClassTeacher))).scalar(), 3)
            user = await UserService.get_user_by_username(db, STUDENTS[0])
            self.assertEqual(user.nickname, "张三")
            self.assertEqual(user.password_hash, "changed-password-hash")
            self.assertFalse(user.requires_identity_confirmation)

    async def test_name_gate_persists_and_teachers_see_it(self):
        headers = await self.login(STUDENTS[0])
        me = (await self.client.get("/api/v1/auth/me", headers=headers)).json()["data"]
        self.assertTrue(me["requires_identity_confirmation"])
        blocked = await self.client.get("/api/v1/todos/", headers=headers)
        self.assertEqual(blocked.status_code, 403)
        bypass = await self.client.put(f"/api/v1/users/{me['id']}", headers=headers, json={"nickname": "绕过"})
        self.assertEqual(bypass.status_code, 403)
        for name in ("", "  ", "a" * 51, "张\n三"):
            response = await self.client.post("/api/v1/auth/identity", headers=headers, json={"name": name})
            self.assertEqual(response.status_code, 422, response.text)
        saved = await self.client.post("/api/v1/auth/identity", headers=headers, json={"name": " 张三 "})
        self.assertEqual(saved.status_code, 200, saved.text)
        self.assertFalse(saved.json()["data"]["requires_identity_confirmation"])
        # Repeated submission cannot accidentally overwrite a completed registration.
        again = await self.client.post("/api/v1/auth/identity", headers=headers, json={"name": "另一个人"})
        self.assertEqual(again.json()["data"]["nickname"], "张三")
        self.assertEqual((await self.client.get("/api/v1/todos/", headers=headers)).status_code, 200)
        headers = await self.login(STUDENTS[0])
        self.assertFalse((await self.client.get("/api/v1/auth/me", headers=headers)).json()["data"]["requires_identity_confirmation"])
        for teacher in TEACHERS:
            roster = await self.client.get("/api/v1/learning-paths/classes/list", headers=await self.login(teacher))
            self.assertEqual(roster.status_code, 200, roster.text)
            group = roster.json()["data"][0]
            self.assertEqual(group["member_count"], 40)
            student = next(m for m in group["members"] if m["username"] == STUDENTS[0])
            self.assertEqual(student["nickname"], "张三")
            self.assertFalse(student["requires_identity_confirmation"])
        # 两个浏览器同时登记只能产生一个姓名，两个响应也应返回同一结果。
        second_headers = await self.login(STUDENTS[1])
        results = await asyncio.gather(*[
            self.client.post("/api/v1/auth/identity", headers=second_headers, json={"name": name})
            for name in ("李四", "王五")
        ])
        for result in results:
            self.assertEqual(result.status_code, 200, result.text)
        self.assertEqual(results[0].json()["data"]["nickname"], results[1].json()["data"]["nickname"])

    async def test_shared_class_permissions_and_unrelated_teacher_denied(self):
        async with self.sessions() as db:
            for teacher in TEACHERS:
                user = await UserService.get_user_by_username(db, teacher)
                self.assertEqual(len(await AccessControlService.accessible_student_ids(db, user)), 40)
                self.assertTrue(await AccessControlService.can_access_student(db, user, account_id(STUDENTS[0])))
                self.assertEqual(len(await LearningPathService.list_classes(db, user.id)), 1)
                self.assertEqual(len(await LearningPathService.list_class_students(db, CLASS_ID, user.id)), 40)
                self.assertEqual(
                    await AssessmentService._own_student_ids(db, user.id, [str(account_id(STUDENTS[0]))]),
                    {str(account_id(STUDENTS[0]))},
                )
            outsider = uuid4()
            self.assertEqual(await LearningPathService.list_classes(db, outsider), [])
            with self.assertRaises(NotFoundError):
                await LearningPathService.get_class(db, CLASS_ID, outsider)

    async def test_paper_sharing_excludes_other_classes_drafts_and_whitelists(self):
        async with self.sessions() as db:
            other_class = ClassGroup(teacher_id=account_id(TEACHERS[0]), name="其他班")
            db.add(other_class)
            await db.flush()
            targets = [
                ("shared", "published", {"type": "class", "ids": [str(CLASS_ID)]}),
                ("draft", "awaiting_review", {"type": "class", "ids": [str(CLASS_ID)]}),
                ("mixed", "published", {"type": "class", "ids": [str(CLASS_ID), str(other_class.id)]}),
                ("individual", "published", {"type": "student", "ids": [str(account_id(STUDENTS[0]))]}),
                ("whitelist", "published", {"type": "class", "ids": [str(CLASS_ID)], "whitelist": [str(uuid4())]}),
                ("empty", "published", {"type": "class", "ids": []}),
            ]
            papers = []
            for title, status, target in targets:
                paper = AssessmentPaper(
                    creator_id=account_id(TEACHERS[0]), title=title,
                    parse_status=status, publish_target=target,
                )
                papers.append(paper)
                db.add(paper)
            await db.commit()
            for teacher in TEACHERS[1:]:
                teacher_id = account_id(teacher)
                self.assertEqual([p.title for p in await AssessmentService.list_papers(db, teacher_id)], ["shared"])
                self.assertEqual((await AssessmentService.get_paper(db, papers[0].id, teacher_id)).title, "shared")
                for paper in papers[1:]:
                    with self.assertRaises(NotFoundError):
                        await AssessmentService.get_paper(db, paper.id, teacher_id)
                analytics = await AssessmentService.get_class_exam_analytics(db, CLASS_ID, teacher_id)
                self.assertEqual(len(analytics["papers"]), 1)
                history = await AssessmentService.list_student_exam_history(db, CLASS_ID, account_id(STUDENTS[0]), teacher_id)
                self.assertEqual(len(history["attempts"]), 1)
            with self.assertRaises(NotFoundError):
                await AssessmentService.get_paper(db, papers[0].id, uuid4())

    async def test_conflict_rolls_back_instead_of_claiming_an_existing_account(self):
        async with self.sessions() as db:
            user = await UserService.get_user_by_username(db, STUDENTS[0])
            user.student_profile.extra_info = {"interview_batch": "other"}
            await db.commit()
            with self.assertRaisesRegex(ValueError, "批次档案异常"):
                async with db.begin():
                    await seed_interview(db)
            self.assertEqual((await db.execute(select(func.count(User.id)))).scalar(), 43)
