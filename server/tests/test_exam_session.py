"""Exam timing and forced collection against an isolated PostgreSQL database."""
import os
import asyncio
import threading
import unittest
from types import SimpleNamespace
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from sqlalchemy import select
import test_interview_1022 as fixtures
from app.interview_1022 import CLASS_ID, STUDENTS, TEACHERS, account_id
from app.models.assessment import AssessmentPaper, AssessmentQuestion, AssessmentAnswer, BehaviorEvent
from app.services.assessment_service import AssessmentService as A
from app.core.exceptions import NotFoundError, ValidationError


@unittest.skipUnless(os.getenv('INTERVIEW_TEST_DATABASE_URL'), 'Requires disposable test DB')
class ExamSessionTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp = fixtures.InterviewTests.asyncSetUp
    asyncTearDown = fixtures.InterviewTests.asyncTearDown

    async def make_exam(self, db, **options):
        p = await A.create_paper(db, account_id(TEACHERS[0]), None, 'Session test')
        await A.save_questions(db, p.id, p.creator_id, [{
            'question_type': 'code', 'stem': 'Print 1', 'language': 'python', 'score': 100,
            'test_cases': [{'input': '', 'expected_output': '1'}],
        }])
        await A.publish_paper(db, p.id, p.creator_id, {'type': 'class', 'ids': [str(CLASS_ID)]}, **options)
        return p

    async def test_background_collection_runs_judge_and_is_idempotent(self):
        async with self.sessions() as db:
            p = await self.make_exam(db)
            attempt = await A.get_or_create_attempt(db, p.id, account_id(STUDENTS[0]))
            questions = await A.get_student_questions(db, p.id, account_id(STUDENTS[0]))
            await A.save_answers(db, attempt.id, account_id(STUDENTS[0]), [{'question_id': questions[0].id, 'answer': 'print(1)'}])
            p.publish_target = {**p.publish_target, 'due_at': (datetime.now(timezone.utc)-timedelta(minutes=2)).isoformat()}
            await db.commit()
            async def judge(session, row):
                answer = (await session.execute(select(AssessmentAnswer).where(AssessmentAnswer.attempt_id == row.id))).scalar_one()
                answer.score, answer.graded = 100, True
                await session.flush()
                return 1, 0
            with patch.object(A, '_run_code_judge', side_effect=judge) as called:
                self.assertEqual(await A.finalize_expired_attempts(db), 1)
                called.assert_awaited_once()
            await db.refresh(attempt)
            self.assertEqual((attempt.status, attempt.score), ('submitted', 100))
            stamp = attempt.submitted_at
            self.assertEqual(await A.finalize_expired_attempts(db), 0)
            self.assertEqual(attempt.submitted_at, stamp)

    async def test_fullscreen_exit_submission_is_optional(self):
        async with self.sessions() as db:
            p = await self.make_exam(db)
            p.publish_target = {**p.publish_target, 'fullscreen_exit_auto_submit': False}
            await db.commit()
            attempt = await A.get_or_create_attempt(db, p.id, account_id(STUDENTS[0]))
            for _ in range(4):
                db.add(BehaviorEvent(user_id=account_id(STUDENTS[0]), session_id='test', attempt_id=attempt.id, event_type='fullscreen_exit'))
            await db.commit()
            self.assertFalse(await A._violation_limit_reached(db, attempt))
            p.publish_target = {**p.publish_target, 'fullscreen_exit_auto_submit': True}
            await db.commit()
            self.assertTrue(await A._violation_limit_reached(db, attempt))

    async def test_schedule_gates_access_without_waiting_for_worker(self):
        async with self.sessions() as db:
            now = datetime.now(timezone.utc)
            p = await self.make_exam(db, publish_at=now+timedelta(minutes=5), due_at=now+timedelta(hours=1))
            with self.assertRaises(NotFoundError):
                await A.get_student_questions(db, p.id, account_id(STUDENTS[0]))
            p.publish_at = now-timedelta(seconds=1)
            await db.commit()
            self.assertEqual(len(await A.get_student_questions(db, p.id, account_id(STUDENTS[0]))), 1)
            attempt = await A.get_or_create_attempt(db, p.id, account_id(STUDENTS[0]))
            p.publish_target = {**p.publish_target, 'due_at': (now-timedelta(minutes=2)).isoformat()}
            await db.commit()
            with self.assertRaises(ValidationError):
                await A.save_answers(db, attempt.id, account_id(STUDENTS[0]), [])
            with self.assertRaises(ValidationError):
                q = (await A.get_student_questions(db, p.id, account_id(STUDENTS[0])))[0]
                await A.code_dry_run(db, attempt.id, account_id(STUDENTS[0]), q.id, 'print(1)')
            await db.rollback()

    async def test_running_selftest_does_not_lock_answer_saving(self):
        async with self.sessions() as db:
            p = await self.make_exam(db)
            student = account_id(STUDENTS[0])
            a = await A.get_or_create_attempt(db, p.id, student)
            q = (await A.get_student_questions(db, p.id, student))[0]
            aid, qid = a.id, q.id
        started, release = threading.Event(), threading.Event()
        def slow_run(*args):
            started.set()
            release.wait(10)
            return SimpleNamespace(status='ok', message='', compile_output='', cases=[])
        async def run():
            async with self.sessions() as db:
                await A.code_dry_run(db, aid, student, qid, 'print(1)')
                await db.commit()
        async def save():
            async with self.sessions() as db:
                await A.save_answers(db, aid, student, [{'question_id': qid, 'answer': 'print(1)'}])
        with patch('app.services.judge_service.dry_run', side_effect=slow_run):
            task = asyncio.create_task(run())
            try:
                for _ in range(500):
                    if started.is_set():
                        break
                    await asyncio.sleep(.01)
                self.assertTrue(started.is_set())
                await asyncio.wait_for(save(), timeout=.5)
            finally:
                release.set()
                await task

    async def test_review_hides_solutions_until_global_deadline(self):
        async with self.sessions() as db:
            p = await self.make_exam(db, due_at=datetime.now(timezone.utc)+timedelta(hours=1))
            student = account_id(STUDENTS[0])
            attempt = await A.get_or_create_attempt(db, p.id, student)
            question = (await A.get_student_questions(db, p.id, student))[0]
            question.answer, question.analysis = 'secret answer', 'secret solution'
            await db.commit()
            await A.submit_attempt(db, attempt.id, student, [])
            review = await A.get_student_review(db, p.id, student)
            self.assertIsNone(review['questions'][0]['reference_answer'])
            self.assertIsNone(review['questions'][0]['analysis'])
            p.publish_target = {**p.publish_target, 'due_at': (datetime.now(timezone.utc)-timedelta(seconds=1)).isoformat()}
            await db.commit()
            review = await A.get_student_review(db, p.id, student)
            self.assertFalse(review['paper']['answers_available'])
            self.assertIsNone(review['questions'][0]['analysis'])
            p.publish_target = {**p.publish_target, 'due_at': (datetime.now(timezone.utc)-timedelta(minutes=1)).isoformat()}
            await db.commit()
            review = await A.get_student_review(db, p.id, student)
            self.assertEqual(review['questions'][0]['analysis'], 'secret solution')

    async def test_pending_review_reports_graded_programming_points(self):
        async with self.sessions() as db:
            p = await self.make_exam(db)
            student = account_id(STUDENTS[0])
            attempt = await A.get_or_create_attempt(db, p.id, student)
            q = (await A.get_student_questions(db, p.id, student))[0]
            db.add(AssessmentAnswer(attempt_id=attempt.id, question_id=q.id, answer='print(1)', score=100, graded=True))
            attempt.status, attempt.score = 'pending_review', 100
            await db.commit()
            review = await A.get_student_review(db, p.id, student)
            self.assertEqual(review['attempt'].get('graded_score'), 100)
            self.assertIsNone(review['attempt']['score'])

    async def test_resume_during_transport_grace_does_not_collect_early(self):
        async with self.sessions() as db:
            p = await self.make_exam(db)
            student = account_id(STUDENTS[0])
            attempt = await A.get_or_create_attempt(db, p.id, student)
            p.publish_target = {**p.publish_target, 'due_at': (datetime.now(timezone.utc)-timedelta(seconds=1)).isoformat()}
            await db.commit()
            with patch.object(A, '_run_code_judge') as judge:
                resumed = await A.get_or_create_attempt(db, p.id, student)
                self.assertEqual(resumed.status, 'in_progress')
                judge.assert_not_called()
