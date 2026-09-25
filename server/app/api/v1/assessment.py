from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Body, Depends, Path
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_staff, require_student
from app.core.database import get_db
from app.models.user import User
from app.schemas.assessment import (
    AssessmentPaperCreateReq,
    AssessmentPaperOut,
    AssessmentPublishReq,
    AssessmentQuestionOut,
    AttemptMonitorOut,
    BehaviorBatchReq,
    BehaviorEventOut,
    ParseStatusOut,
    QuestionsSaveReq,
    StudentAnswersReq,
    StudentAnswersOut,
    StudentAttemptOut,
    StudentPaperOut,
    AttemptAnswerOut,
    GradeAttemptReq,
    PaperAnalyticsOut,
    StudentQuestionOut,
)
from app.schemas.common import BaseResponse
from app.services.assessment_service import AssessmentService

router = APIRouter()


@router.post("/papers", response_model=BaseResponse[AssessmentPaperOut], summary="创建发题任务并触发 AI 拆题")
async def create_paper(
    req: AssessmentPaperCreateReq = Body(...),
    current_user: User = Depends(require_staff),
    db: AsyncSession = Depends(get_db),
):
    paper = await AssessmentService.create_paper(db, current_user.id, req.file_id, req.title, req.description)
    return BaseResponse.success(data=AssessmentPaperOut.model_validate(paper), message="拆题任务已提交")


@router.post(
    "/papers/{paper_id}/reparse",
    response_model=BaseResponse[AssessmentPaperOut],
    summary="重新拆题（pending / parsing / failed 卡住时）",
)
async def reparse_paper(
    paper_id: UUID = Path(...),
    current_user: User = Depends(require_staff),
    db: AsyncSession = Depends(get_db),
):
    paper = await AssessmentService.reparse_paper(db, paper_id, current_user.id)
    return BaseResponse.success(data=AssessmentPaperOut.model_validate(paper), message="已重新提交拆题")


@router.get(
    "/papers/{paper_id}/analytics",
    response_model=BaseResponse[PaperAnalyticsOut],
    summary="试卷分析聚合（概览/分数分布/逐题正确率与耗时/行为分布）",
)
async def get_paper_analytics(
    paper_id: UUID = Path(...),
    current_user: User = Depends(require_staff),
    db: AsyncSession = Depends(get_db),
):
    data = await AssessmentService.get_paper_analytics(db, paper_id, current_user.id)
    return BaseResponse.success(data=PaperAnalyticsOut(**data), message="获取成功")


@router.get("/papers", response_model=BaseResponse[List[AssessmentPaperOut]], summary="教师试卷列表")
async def list_papers(
    current_user: User = Depends(require_staff),
    db: AsyncSession = Depends(get_db),
):
    papers = await AssessmentService.list_papers(db, current_user.id)
    return BaseResponse.success(data=[AssessmentPaperOut.model_validate(p) for p in papers], message="获取成功")


@router.get("/papers/{paper_id}", response_model=BaseResponse[AssessmentPaperOut], summary="试卷详情")
async def get_paper(
    paper_id: UUID = Path(...),
    current_user: User = Depends(require_staff),
    db: AsyncSession = Depends(get_db),
):
    paper = await AssessmentService.get_paper(db, paper_id, current_user.id)
    return BaseResponse.success(data=AssessmentPaperOut.model_validate(paper), message="获取成功")


@router.get("/papers/{paper_id}/parse-status", response_model=BaseResponse[ParseStatusOut], summary="拆题解析进度")
async def get_parse_status(
    paper_id: UUID = Path(...),
    current_user: User = Depends(require_staff),
    db: AsyncSession = Depends(get_db),
):
    paper = await AssessmentService.get_paper(db, paper_id, current_user.id)
    progress = await AssessmentService.get_parse_progress(paper_id)
    return BaseResponse.success(
        data=ParseStatusOut(
            parse_status=paper.parse_status,
            parse_progress=progress,
            parse_error=paper.parse_error,
            question_count=paper.question_count,
            total_score=paper.total_score,
        ),
        message="获取成功",
    )


@router.get(
    "/papers/{paper_id}/questions",
    response_model=BaseResponse[List[AssessmentQuestionOut]],
    summary="试卷题目列表（供校对）",
)
async def list_questions(
    paper_id: UUID = Path(...),
    current_user: User = Depends(require_staff),
    db: AsyncSession = Depends(get_db),
):
    questions = await AssessmentService.list_questions(db, paper_id, current_user.id)
    return BaseResponse.success(
        data=[AssessmentQuestionOut.model_validate(q) for q in questions],
        message="获取成功",
    )


@router.put(
    "/papers/{paper_id}/questions",
    response_model=BaseResponse[AssessmentPaperOut],
    summary="保存人工校对后的题目",
)
async def save_questions(
    paper_id: UUID = Path(...),
    req: QuestionsSaveReq = Body(...),
    current_user: User = Depends(require_staff),
    db: AsyncSession = Depends(get_db),
):
    questions = [q.model_dump() for q in req.questions]
    paper = await AssessmentService.save_questions(db, paper_id, current_user.id, questions)
    return BaseResponse.success(data=AssessmentPaperOut.model_validate(paper), message="题目已保存")


@router.post(
    "/papers/{paper_id}/publish",
    response_model=BaseResponse[AssessmentPaperOut],
    summary="发布试卷（立即或预约）",
)
async def publish_paper(
    paper_id: UUID = Path(...),
    req: AssessmentPublishReq = Body(...),
    current_user: User = Depends(require_staff),
    db: AsyncSession = Depends(get_db),
):
    paper = await AssessmentService.publish_paper(
        db,
        paper_id,
        current_user.id,
        req.publish_target,
        req.publish_at,
        req.due_at,
    )
    return BaseResponse.success(data=AssessmentPaperOut.model_validate(paper), message="发布成功")


@router.get(
    "/papers/{paper_id}/attempts",
    response_model=BaseResponse[List[AttemptMonitorOut]],
    summary="教师查看试卷作答与监考数据",
)
async def list_paper_attempts(
    paper_id: UUID = Path(...),
    current_user: User = Depends(require_staff),
    db: AsyncSession = Depends(get_db),
):
    attempts = await AssessmentService.list_paper_attempts(db, paper_id, current_user.id)
    return BaseResponse.success(
        data=[AttemptMonitorOut(**a) for a in attempts],
        message="获取成功",
    )


@router.get(
    "/attempts/{attempt_id}/behavior",
    response_model=BaseResponse[List[BehaviorEventOut]],
    summary="教师查看某次作答的行为事件明细",
)
async def list_attempt_behavior(
    attempt_id: UUID = Path(...),
    current_user: User = Depends(require_staff),
    db: AsyncSession = Depends(get_db),
):
    events = await AssessmentService.list_attempt_behavior(db, attempt_id, current_user.id)
    return BaseResponse.success(
        data=[BehaviorEventOut(**e) for e in events],
        message="获取成功",
    )


@router.get(
    "/attempts/{attempt_id}/answers",
    response_model=BaseResponse[List[AttemptAnswerOut]],
    summary="教师查看某次作答的逐题答案（用于批改主观题）",
)
async def list_attempt_answers(
    attempt_id: UUID = Path(...),
    current_user: User = Depends(require_staff),
    db: AsyncSession = Depends(get_db),
):
    answers = await AssessmentService.list_attempt_answers(db, attempt_id, current_user.id)
    return BaseResponse.success(
        data=[AttemptAnswerOut(**a) for a in answers],
        message="获取成功",
    )


@router.post(
    "/attempts/{attempt_id}/grade",
    response_model=BaseResponse[StudentAttemptOut],
    summary="教师批改主观题并重算总分",
)
async def grade_attempt(
    attempt_id: UUID = Path(...),
    req: GradeAttemptReq = Body(...),
    current_user: User = Depends(require_staff),
    db: AsyncSession = Depends(get_db),
):
    grades = [{"question_id": g.question_id, "score": g.score} for g in req.grades]
    attempt = await AssessmentService.grade_attempt(db, attempt_id, current_user.id, grades)
    return BaseResponse.success(data=StudentAttemptOut.model_validate(attempt), message="批改已保存")


@router.get(
    "/student/papers",
    response_model=BaseResponse[List[StudentPaperOut]],
    summary="学生端已发布试卷列表",
)
async def student_list_papers(
    current_user: User = Depends(require_student),
    db: AsyncSession = Depends(get_db),
):
    papers = await AssessmentService.list_student_papers(db, current_user.id)
    return BaseResponse.success(
        data=[StudentPaperOut(**p) for p in papers],
        message="获取成功",
    )


@router.get(
    "/student/papers/{paper_id}/questions",
    response_model=BaseResponse[List[StudentQuestionOut]],
    summary="学生端查看试卷题目（不含答案与解析）",
)
async def student_get_questions(
    paper_id: UUID = Path(...),
    current_user: User = Depends(require_student),
    db: AsyncSession = Depends(get_db),
):
    questions = await AssessmentService.get_student_questions(db, paper_id, current_user.id)
    return BaseResponse.success(
        data=[StudentQuestionOut.model_validate(q) for q in questions],
        message="获取成功",
    )


@router.post(
    "/student/papers/{paper_id}/attempts",
    response_model=BaseResponse[StudentAttemptOut],
    summary="学生开始或恢复作答",
)
async def student_start_attempt(
    paper_id: UUID = Path(...),
    current_user: User = Depends(require_student),
    db: AsyncSession = Depends(get_db),
):
    attempt = await AssessmentService.get_or_create_attempt(db, paper_id, current_user.id)
    return BaseResponse.success(data=StudentAttemptOut.model_validate(attempt), message="获取成功")


@router.put(
    "/student/attempts/{attempt_id}/answers",
    response_model=BaseResponse[Optional[StudentAttemptOut]],
    summary="学生作答草稿自动保存",
)
async def student_save_answers(
    attempt_id: UUID = Path(...),
    req: StudentAnswersReq = Body(...),
    current_user: User = Depends(require_student),
    db: AsyncSession = Depends(get_db),
):
    answers = [{"question_id": a.question_id, "answer": a.answer} for a in req.answers]
    forced = await AssessmentService.save_answers(db, attempt_id, current_user.id, answers)
    if forced is not None:
        # 违规超限触发了服务端强制交卷，把结果回给前端让它切到已交卷态
        return BaseResponse.success(
            data=StudentAttemptOut.model_validate(forced),
            message="已保存并自动交卷",
        )
    return BaseResponse.success(message="已保存")


@router.get(
    "/student/papers/{paper_id}/answers",
    response_model=BaseResponse[StudentAnswersOut],
    summary="学生回读自己已保存的作答",
)
async def student_get_answers(
    paper_id: UUID = Path(...),
    current_user: User = Depends(require_student),
    db: AsyncSession = Depends(get_db),
):
    data = await AssessmentService.get_student_answers(db, paper_id, current_user.id)
    return BaseResponse.success(
        data=StudentAnswersOut(**data),
        message="获取成功",
    )


@router.post(
    "/student/attempts/{attempt_id}/submit",
    response_model=BaseResponse[StudentAttemptOut],
    summary="学生交卷",
)
async def student_submit(
    attempt_id: UUID = Path(...),
    req: StudentAnswersReq = Body(...),
    current_user: User = Depends(require_student),
    db: AsyncSession = Depends(get_db),
):
    answers = [{"question_id": a.question_id, "answer": a.answer} for a in req.answers]
    attempt, answers_ignored = await AssessmentService.submit_attempt(
        db, attempt_id, current_user.id, answers
    )
    out = StudentAttemptOut.model_validate(attempt)
    out.answers_ignored = answers_ignored
    message = "已交卷，但超过截止时间的作答未计入" if answers_ignored else "交卷成功"
    return BaseResponse.success(data=out, message=message)


@router.post(
    "/student/behavior/batch",
    response_model=BaseResponse,
    summary="学生作答行为事件批量上报",
)
async def student_behavior_batch(
    req: BehaviorBatchReq = Body(...),
    current_user: User = Depends(require_student),
    db: AsyncSession = Depends(get_db),
):
    events = [
        {"event_type": e.event_type, "payload": e.payload, "occurred_at": e.occurred_at}
        for e in req.events
    ]
    count = await AssessmentService.batch_save_behavior(
        db, current_user.id, req.session_id, events, req.attempt_id
    )
    return BaseResponse.success(message=f"已记录 {count} 条行为")