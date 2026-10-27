"""通过与手动命题 API 相同的服务创建 1022 二面草稿。"""
import asyncio
import json
from datetime import datetime
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from app.core.database import SessionLocal, engine
from app.interview_1022 import TEACHERS, CLASS_ID, account_id
from app.models.assessment import AssessmentPaper
from app.services.assessment_service import AssessmentService

PAPER_ID = uuid5(NAMESPACE_URL, "studypartner:interview:1022:paper:v1")
START_AT = datetime.fromisoformat('2026-10-22T14:50:00+08:00')
END_AT = datetime.fromisoformat('2026-10-22T15:50:00+08:00')


async def schedule_exam(db, paper):
    # 仅升级未配置发布对象的本次草稿。已有人工安排和作答不覆盖。
    if paper.parse_status != 'awaiting_review' or paper.publish_target:
        return paper
    if paper.description:
        paper.description = paper.description.replace(
            '请在发布前自行设置班级与考试时间。', '本场时间为 2026-10-22 14:50～15:50（北京时间）。'
        )
    return await AssessmentService.publish_paper(
        db, paper.id, paper.creator_id,
        {'type': 'class', 'ids': [str(CLASS_ID)]},
        publish_at=START_AT, due_at=END_AT, require_fullscreen=True,
        fullscreen_exit_auto_submit=False,
    )


async def ensure_exam(db):
    existing = await db.get(AssessmentPaper, PAPER_ID)
    if existing:
        if existing.deleted_at or existing.creator_id != account_id(TEACHERS[0]):
            raise ValueError("1022 试卷标识冲突或已删除，未覆盖")
        return await schedule_exam(db, existing), False
    data = json.loads(Path(__file__).with_name("data").joinpath("exam_1022.json").read_text(encoding="utf-8"))
    paper = await AssessmentService.create_paper(
        db, account_id(TEACHERS[0]), None, data["title"],
        "2026年10月22日14:50～15:50（北京时间）；五道编程题，共140分，支持 Python、Java、C、C++。",
        paper_id=PAPER_ID,
    )
    paper = await AssessmentService.save_questions(db, paper.id, paper.creator_id, data["questions"])
    return await schedule_exam(db, paper), True


async def main():
    try:
        async with SessionLocal() as db:
            paper, created = await ensure_exam(db)
            print(f"{'已创建' if created else '已保留'}：{paper.title} / {paper.id} / {paper.parse_status} / {paper.question_count} 题")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
