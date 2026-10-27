"""Explicit, additive upgrade of the unopened 1022 exam; never rebuild existing questions."""
import argparse
import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import func, select
from app.core.database import SessionLocal, engine
from app.exam_1022 import PAPER_ID
from app.interview_1022 import TEACHERS, account_id
from app.models.assessment import AssessmentAttempt, AssessmentPaper, AssessmentQuestion


def load_questions():
    return json.loads(Path(__file__).with_name('data').joinpath('exam_1022.json').read_text(encoding='utf-8'))['questions']


def matches(row, expected):
    return all(getattr(row, key) == value for key, value in expected.items() if key != 'order_index')


async def upgrade(db, *, check_only=False):
    questions = load_questions()
    assert len(questions) == 5 and sum(q['score'] for q in questions) == 140
    paper = (await db.execute(select(AssessmentPaper).where(AssessmentPaper.id == PAPER_ID).with_for_update())).scalar_one_or_none()
    if not paper or paper.deleted_at or paper.creator_id != account_id(TEACHERS[0]):
        raise ValueError('1022 exam missing or ownership differs; start the original deployment first')
    rows = list((await db.execute(select(AssessmentQuestion).where(AssessmentQuestion.paper_id == PAPER_ID).order_by(AssessmentQuestion.order_index))).scalars())
    if len(rows) == 5 and all(matches(row, q) and row.order_index == i for i, (row, q) in enumerate(zip(rows, questions))):
        if paper.question_count != 5 or paper.total_score != 140:
            raise ValueError('Existing five-question exam has inconsistent totals')
        return False
    if paper.parse_status != 'awaiting_review':
        raise ValueError('Exam is not an unopened draft; no changes applied')
    if paper.publish_at is not None and datetime.now(timezone.utc) >= paper.publish_at:
        raise ValueError('Exam start time has arrived; no changes applied')
    count = await db.scalar(select(func.count()).select_from(AssessmentAttempt).where(AssessmentAttempt.paper_id == PAPER_ID))
    if count:
        raise ValueError('Exam already has student attempts; no changes applied')
    old_indexes = (0, 3, 4)
    if len(rows) != 3 or paper.question_count != 3 or paper.total_score != 100:
        raise ValueError('Expected original three-question, 100-point exam')
    if not all(matches(row, questions[new_index]) and row.order_index == i for i, (row, new_index) in enumerate(zip(rows, old_indexes))):
        raise ValueError('Original questions differ from the delivered version; no changes applied')
    if check_only:
        return True
    for row, new_index in zip(rows, old_indexes):
        row.order_index = new_index
    for i in (1, 2):
        db.add(AssessmentQuestion(id=uuid5(NAMESPACE_URL, f'studypartner:interview:1022:extra:{i}'),
                                 paper_id=PAPER_ID, **questions[i]))
    paper.question_count, paper.total_score = 5, 140
    if paper.description:
        paper.description = paper.description.replace('三道编程题', '五道编程题，共140分')
    await db.flush()
    return True


async def main(check_only):
    try:
        async with SessionLocal() as db:
            changed = await upgrade(db, check_only=check_only)
            if check_only:
                await db.rollback()
            else:
                await db.commit()
            print(('READY: additive upgrade allowed' if changed else 'ALREADY UPDATED: five questions, 140 points') if check_only
                  else ('UPDATED: five questions, 140 points; original question IDs preserved' if changed else 'UNCHANGED: already updated'))
    finally:
        await engine.dispose()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true', help='Validate without changing any data')
    args = parser.parse_args()
    asyncio.run(main(args.check))
