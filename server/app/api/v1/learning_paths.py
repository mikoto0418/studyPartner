from typing import Any, Dict, List
from uuid import UUID

from fastapi import APIRouter, Body, Depends, Path
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_staff
from app.core.database import get_db
from app.models.user import User
from app.schemas.common import BaseResponse
from app.schemas.learning_path import (
    ClassCreate,
    ClassOut,
    ClassOverviewOut,
    LearningNodeReviewReq,
    LearningNodeSubmitReq,
    LearningInsightOut,
    LearningInsightStatusUpdate,
    LearningPathCreate,
    LearningPathDetailOut,
    LearningPathGenerateReq,
    LearningPathPlanOut,
    LearningPathStudentProgressOut,
    LearningPathTaskOut,
    LearningPathUpdate,
    StudentGrowthOverviewOut,
)
from app.services.learning_path_service import LearningPathService

router = APIRouter()


@router.post("/generate", response_model=BaseResponse[LearningPathPlanOut], summary="根据教师粗略规划生成学习路径草案")
async def generate_learning_path_plan(
    req: LearningPathGenerateReq = Body(...),
    current_user: User = Depends(require_staff),
):
    plan = await LearningPathService.generate_plan(
        req.goal,
        req.planning_text,
        req.title,
        user_id=current_user.id,
        enable_web_research=req.enable_web_research,
    )
    return BaseResponse.success(data=LearningPathPlanOut(**plan), message="学习路径草案已生成")


@router.post("/", response_model=BaseResponse[LearningPathTaskOut], summary="创建学习路径任务")
async def create_learning_path(
    path_in: LearningPathCreate = Body(...),
    current_user: User = Depends(require_staff),
    db: AsyncSession = Depends(get_db),
):
    task = await LearningPathService.create_path(db, current_user.id, path_in)
    summary = await LearningPathService._task_summary(db, task)
    return BaseResponse.success(data=LearningPathTaskOut(**summary), message="学习路径任务已创建")


@router.get("/", response_model=BaseResponse[List[LearningPathTaskOut]], summary="教师获取学习路径任务列表")
async def list_teacher_learning_paths(
    current_user: User = Depends(require_staff),
    db: AsyncSession = Depends(get_db),
):
    tasks = await LearningPathService.list_teacher_paths(db, current_user.id)
    return BaseResponse.success(data=[LearningPathTaskOut(**task) for task in tasks], message="获取成功")


@router.get("/student", response_model=BaseResponse[List[LearningPathTaskOut]], summary="学生获取自己的学习路径任务")
async def list_my_learning_paths(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    tasks = await LearningPathService.list_student_paths(db, current_user.id)
    return BaseResponse.success(data=[LearningPathTaskOut(**task) for task in tasks], message="获取成功")


@router.get("/{task_id}", response_model=BaseResponse[LearningPathDetailOut], summary="获取学习路径详情")
async def get_learning_path_detail(
    task_id: UUID = Path(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    detail = await LearningPathService.get_path_detail(db, task_id, current_user)
    return BaseResponse.success(data=LearningPathDetailOut(**detail), message="获取成功")


@router.get("/{task_id}/students/{student_id}", response_model=BaseResponse[LearningPathStudentProgressOut], summary="教师查看学生学习路径进度")
async def get_learning_path_student_progress(
    task_id: UUID = Path(...),
    student_id: UUID = Path(...),
    current_user: User = Depends(require_staff),
    db: AsyncSession = Depends(get_db),
):
    detail = await LearningPathService.get_student_path_progress(db, task_id, student_id, current_user.id)
    return BaseResponse.success(data=LearningPathStudentProgressOut(**detail), message="获取成功")


@router.put("/{task_id}", response_model=BaseResponse[LearningPathTaskOut], summary="教师微调学习路径任务")
async def update_learning_path(
    task_id: UUID = Path(...),
    path_in: LearningPathUpdate = Body(...),
    current_user: User = Depends(require_staff),
    db: AsyncSession = Depends(get_db),
):
    task = await LearningPathService.update_path(db, task_id, current_user.id, path_in)
    summary = await LearningPathService._task_summary(db, task)
    return BaseResponse.success(data=LearningPathTaskOut(**summary), message="学习路径已更新")


@router.post("/{task_id}/nodes/{node_id}/submit", response_model=BaseResponse[Dict[str, Any]], summary="学生提交学习路径节点")
async def submit_learning_node(
    task_id: UUID = Path(...),
    node_id: UUID = Path(...),
    submission_in: LearningNodeSubmitReq = Body(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    submission = await LearningPathService.submit_node(db, task_id, node_id, current_user.id, submission_in)
    return BaseResponse.success(
        data={
            "id": str(submission.id),
            "task_id": str(submission.task_id),
            "node_id": str(submission.node_id),
            "review_status": submission.review_status,
            "created_at": submission.created_at.isoformat(),
        },
        message="节点已提交",
    )


@router.post("/submissions/{submission_id}/review", response_model=BaseResponse[Dict[str, Any]], summary="教师批改学习路径节点提交")
async def review_learning_node_submission(
    submission_id: UUID = Path(...),
    review_in: LearningNodeReviewReq = Body(...),
    current_user: User = Depends(require_staff),
    db: AsyncSession = Depends(get_db),
):
    submission = await LearningPathService.review_submission(db, submission_id, current_user.id, review_in)
    return BaseResponse.success(
        data={
            "id": str(submission.id),
            "review_status": submission.review_status,
            "score": submission.score,
            "feedback": submission.feedback,
            "follow_up": submission.follow_up,
            "reviewed_at": submission.reviewed_at.isoformat() if submission.reviewed_at else None,
        },
        message="批改完成",
    )


@router.post("/classes", response_model=BaseResponse[ClassOut], summary="教师创建班级")
async def create_class(
    class_in: ClassCreate = Body(...),
    current_user: User = Depends(require_staff),
    db: AsyncSession = Depends(get_db),
):
    class_group = await LearningPathService.create_class(db, current_user.id, class_in)
    class_group = await LearningPathService.get_class(db, class_group.id, current_user.id)
    return BaseResponse.success(data=ClassOut(**LearningPathService._class_to_dict(class_group)), message="班级已创建")


@router.get("/classes/list", response_model=BaseResponse[List[ClassOut]], summary="教师获取班级列表")
async def list_classes(
    current_user: User = Depends(require_staff),
    db: AsyncSession = Depends(get_db),
):
    classes = await LearningPathService.list_classes(db, current_user.id)
    data = [ClassOut(**LearningPathService._class_to_dict(item)) for item in classes]
    return BaseResponse.success(data=data, message="获取成功")


@router.get("/classes/{class_id}/overview", response_model=BaseResponse[ClassOverviewOut], summary="班级 Memory 概况")
async def get_class_overview(
    class_id: UUID = Path(...),
    current_user: User = Depends(require_staff),
    db: AsyncSession = Depends(get_db),
):
    overview = await LearningPathService.get_class_overview(db, class_id, current_user.id)
    return BaseResponse.success(data=ClassOverviewOut(**overview), message="获取成功")


@router.patch("/insights/{insight_id}/status", response_model=BaseResponse[LearningInsightOut], summary="更新班级洞察状态")
async def update_learning_insight_status(
    insight_id: UUID = Path(...),
    status_in: LearningInsightStatusUpdate = Body(...),
    current_user: User = Depends(require_staff),
    db: AsyncSession = Depends(get_db),
):
    insight = await LearningPathService.update_insight_status(db, insight_id, current_user.id, status_in)
    return BaseResponse.success(data=LearningInsightOut(**insight), message="洞察状态已更新")


@router.get("/growth/{student_id}", response_model=BaseResponse[StudentGrowthOverviewOut], summary="学生成长数据全览")
async def get_student_growth(
    student_id: UUID = Path(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    overview = await LearningPathService.get_student_growth(db, student_id, current_user)
    return BaseResponse.success(data=StudentGrowthOverviewOut(**overview), message="获取成功")
