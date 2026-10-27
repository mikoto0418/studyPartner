"""Monitoring classifications and storage against the explicitly disposable test DB."""
import asyncio
import os
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

from sqlalchemy import select, func
import test_interview_1022 as fixtures
from app.core.exceptions import PermissionDenied, ValidationError
from app.interview_1022 import CLASS_ID, STUDENTS, TEACHERS, account_id
from app.models.assessment import BehaviorEvent
from app.services.assessment_service import AssessmentService as A


class AttentionTests(unittest.TestCase):
    def events(self, kinds):
        start = datetime.now(timezone.utc)
        return [SimpleNamespace(id=uuid4(), attempt_id='a', session_id='s',
            event_type=kind, payload=payload, created_at=start + timedelta(seconds=i),
            occurred_at=start + timedelta(seconds=i)) for i, (kind, payload) in enumerate(kinds)]

    def test_blur_hidden_form_one_leave_and_return_opens_next_episode(self):
        events = self.events([(k, {}) for k in (
            'focus_loss', 'visibility_hidden', 'focus_gain', 'visibility_visible', 'focus_loss')])
        self.assertEqual(A.attention_events(events), [events[0], events[-1]])

    def test_editor_helpers_and_window_heuristics_are_not_violations(self):
        events = self.events([(k, {}) for k in (
            'devtools_open', 'blocked_input', 'blocked_copy', 'blocked_cut', 'blocked_selection',
            'blocked_contextmenu', 'blocked_shortcut', 'fullscreen_denied', 'answer_edit')])
        self.assertEqual(A.attention_events(events), [])

    def test_new_episode_ids_and_real_restricted_actions(self):
        events = self.events([
            ('page_leave', {'episode_id': 'one'}), ('page_return', {'episode_id': 'one'}),
            ('page_leave', {'episode_id': 'one'}), ('page_return', {'episode_id': 'one'}),
            ('page_leave', {'episode_id': 'two'}), ('fullscreen_exit', {}),
            ('blocked_insert', {'input_type': 'insertReplacementText'}),
            ('blocked_paste', {}),
        ])
        self.assertEqual(A.attention_events(events), [events[i] for i in (0, 4, 5, 7)])


@unittest.skipUnless(os.getenv('INTERVIEW_TEST_DATABASE_URL'), 'Requires disposable *_test DB')
class MonitoringTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp = fixtures.InterviewTests.asyncSetUp
    asyncTearDown = fixtures.InterviewTests.asyncTearDown

    async def exam(self, db):
        teacher, student = account_id(TEACHERS[0]), account_id(STUDENTS[0])
        paper = await A.create_paper(db, teacher, None, 'Monitor regression')
        await A.save_questions(db, paper.id, teacher, [
            {'question_type': 'code', 'stem': str(i), 'language': 'multi', 'score': 50,
             'test_cases': [{'input': '', 'expected_output': '1'}]} for i in range(2)])
        await A.publish_paper(db, paper.id, teacher, {'type': 'class', 'ids': [str(CLASS_ID)]},
            require_fullscreen=True, fullscreen_exit_auto_submit=True)
        attempt = await A.get_or_create_attempt(db, paper.id, student)
        questions = await A.get_student_questions(db, paper.id, student)
        return teacher, student, paper, attempt, questions

    async def test_saved_code_empty_questions_and_grading_permissions(self):
        async with self.sessions() as db:
            teacher, student, paper, attempt, questions = await self.exam(db)
            before = await A.list_attempt_answers(db, attempt.id, teacher)
            self.assertEqual(len(before), 2)
            self.assertTrue(all(not a['has_saved_answer'] and a['answer'] is None for a in before))
            await A.save_answers(db, attempt.id, student, [{'question_id': questions[0].id,
                'answer': {'language': 'cpp', 'code': 'int main() { return 0; }'}}])
            answers = await A.list_attempt_answers(db, attempt.id, teacher)
            self.assertEqual(answers[0]['language'], 'cpp')
            self.assertIsNotNone(answers[0]['saved_at'])
            self.assertEqual(answers[0]['answer']['code'], 'int main() { return 0; }')
            self.assertFalse(answers[1]['has_saved_answer'])
            with self.assertRaises((PermissionDenied, ValidationError)):
                await A.grade_attempt(db, attempt.id, teacher, [])
            with self.assertRaises(PermissionDenied):
                await A.list_attempt_answers(db, attempt.id, account_id(STUDENTS[1]))

    async def test_replayed_events_do_not_force_collection_or_cross_student_boundary(self):
        async with self.sessions() as db:
            teacher, student, paper, attempt, _ = await self.exam(db)
            aid, pid = attempt.id, paper.id
            event = {'event_id': uuid4(), 'event_type': 'fullscreen_exit'}
            self.assertEqual(await A.batch_save_behavior(db, student, 'one', [event], aid), 1)
            self.assertEqual(await A.batch_save_behavior(db, student, 'retry', [event], aid), 0)
            self.assertFalse(await A._violation_limit_reached(db, attempt))
            with self.assertRaises(PermissionDenied):
                await A.batch_save_behavior(db, account_id(STUDENTS[1]), 'x', [event], aid)
        async def replay():
            async with self.sessions() as session:
                return await A.batch_save_behavior(session, student, 'parallel', [event], aid)
        self.assertEqual(await asyncio.gather(replay(), replay()), [0, 0])
        async with self.sessions() as db:
            rows = await A.list_paper_attempts(db, pid, teacher)
            self.assertEqual(rows[0]['fullscreen_exit_count'], 1)
            self.assertEqual(rows[0]['flagged_count'], 1)
            count = await db.scalar(select(func.count()).select_from(BehaviorEvent).where(BehaviorEvent.attempt_id == aid))
            self.assertEqual(count, 1)
