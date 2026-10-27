"""Exercise the offline additive updater on disposable PostgreSQL, preserving IDs and settings."""
import os
import unittest
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from sqlalchemy import select
import test_interview_1022 as fixtures
from app.exam_1022 import PAPER_ID, START_AT, END_AT
from app.interview_1022 import CLASS_ID, TEACHERS, STUDENTS, account_id
from app.models.assessment import AssessmentAttempt, AssessmentPaper, AssessmentQuestion
from app.services.assessment_service import AssessmentService as A
from app.update_exam_1022 import upgrade, load_questions


@unittest.skipUnless(os.getenv('INTERVIEW_TEST_DATABASE_URL'), 'Requires disposable test DB')
class ExamUpgradeTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp = fixtures.InterviewTests.asyncSetUp
    asyncTearDown = fixtures.InterviewTests.asyncTearDown

    async def original(self, db):
        p = await A.create_paper(db, account_id(TEACHERS[0]), None, '1022二面', '三道编程题', paper_id=PAPER_ID)
        q = load_questions()
        await A.save_questions(db, p.id, p.creator_id, [q[i] for i in (0,3,4)])
        await A.publish_paper(db, p.id, p.creator_id, {'type':'class','ids':[str(CLASS_ID)]},
                              publish_at=datetime.now(timezone.utc)+timedelta(hours=1),
                              due_at=datetime.now(timezone.utc)+timedelta(hours=2),
                              require_fullscreen=True, fullscreen_exit_auto_submit=False)
        return p

    async def test_addition_preserves_original_ids_and_configuration_and_is_idempotent(self):
        async with self.sessions() as db:
            p = await self.original(db)
            rows = await A.list_questions(db, p.id, p.creator_id)
            before = [{c.name:deepcopy(getattr(row,c.name)) for c in AssessmentQuestion.__table__.columns} for row in rows]
            settings = (p.publish_at, deepcopy(p.publish_target), p.parse_status)
            self.assertTrue(await upgrade(db, check_only=True))
            self.assertEqual(p.question_count,3)
            self.assertTrue(await upgrade(db))
            await db.commit()
            saved = await A.list_questions(db, p.id, p.creator_id)
            self.assertEqual((p.question_count,p.total_score),(5,140))
            self.assertEqual((p.publish_at,p.publish_target,p.parse_status),settings)
            for old,new_index in zip(before,(0,3,4)):
                for key,val in old.items():
                    if key not in ('order_index','updated_at'):
                        self.assertEqual(getattr(saved[new_index],key),val,key)
            self.assertFalse(await upgrade(db))
            self.assertEqual(len(await A.list_questions(db,p.id,p.creator_id)),5)

    async def test_refuses_existing_attempts(self):
        async with self.sessions() as db:
            p=await self.original(db)
            db.add(AssessmentAttempt(paper_id=p.id,student_id=account_id(STUDENTS[0])))
            await db.commit()
            with self.assertRaisesRegex(ValueError,'attempts'):
                await upgrade(db)
            self.assertEqual(p.question_count,3)

    async def test_refuses_started_or_edited_exam(self):
        async with self.sessions() as db:
            p=await self.original(db)
            p.publish_at=datetime.now(timezone.utc)-timedelta(seconds=1)
            await db.commit()
            with self.assertRaisesRegex(ValueError,'start time'):
                await upgrade(db)
            p.publish_at=datetime.now(timezone.utc)+timedelta(hours=1)
            rows=await A.list_questions(db,p.id,p.creator_id)
            rows[0].stem='teacher changed this question'
            await db.commit()
            with self.assertRaisesRegex(ValueError,'differ'):
                await upgrade(db)
