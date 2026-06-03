from typing import List, Dict, Any
from uuid import UUID
from fastapi import APIRouter, Depends, Body, Path
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.schemas.common import BaseResponse
from app.schemas.task import TaskOut, TaskCreate, TaskSubmissionOut, TaskSubmissionCreate, TaskSubmissionReview
from app.services.task_service import TaskService
from app.api.deps import get_current_user, require_staff
from app.models.user import User

router = APIRouter()

@router.get("/student", response_model=BaseResponse[List[Dict[str, Any]]], summary="获取指派给我的任务列表")
async def list_my_tasks(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    tasks = await TaskService.list_student_tasks(db, user_id=current_user.id)
    # Convert IDs to string for JSON serialization
    serialized_tasks = []
    for t in tasks:
        t_copy = t.copy()
        t_copy["id"] = str(t_copy["id"])
        if t_copy.get("attachment_ids"):
            t_copy["attachment_ids"] = [str(x) for x in t_copy["attachment_ids"]]
        serialized_tasks.append(t_copy)
    return BaseResponse.success(data=serialized_tasks, message="获取成功")

@router.get("/", response_model=BaseResponse[List[TaskOut]], summary="获取教师创建的任务列表")
async def list_teacher_tasks(
    current_user: User = Depends(require_staff),
    db: AsyncSession = Depends(get_db)
):
    tasks = await TaskService.list_teacher_created_tasks(db, teacher_id=current_user.id)
    return BaseResponse.success(data=[TaskOut.from_attributes(t) for t in tasks], message="获取成功")

@router.post("/", response_model=BaseResponse[TaskOut], summary="发布教学任务")
async def create_task(
    task_in: TaskCreate = Body(...),
    current_user: User = Depends(require_staff),
    db: AsyncSession = Depends(get_db)
):
    task = await TaskService.create_task(db, creator_id=current_user.id, task_in=task_in)
    return BaseResponse.success(data=TaskOut.from_attributes(task), message="任务发布成功")

@router.post("/{task_id}/submit", response_model=BaseResponse[TaskSubmissionOut], summary="学生提交任务作业")
async def submit_task(
    task_id: UUID = Path(..., description="任务ID"),
    submission_in: TaskSubmissionCreate = Body(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    submission = await TaskService.submit_task(
        db, task_id=task_id, user_id=current_user.id, submission_in=submission_in
    )
    return BaseResponse.success(data=TaskSubmissionOut.from_attributes(submission), message="作业提交成功")

@router.post("/submissions/{submission_id}/review", response_model=BaseResponse[TaskSubmissionOut], summary="教师审核学生作业")
async def review_submission(
    submission_id: UUID = Path(..., description="作业提交记录ID"),
    review_in: TaskSubmissionReview = Body(...),
    current_user: User = Depends(require_staff),
    db: AsyncSession = Depends(get_db)
):
    submission = await TaskService.review_submission(
        db, submission_id=submission_id, reviewer_id=current_user.id, review_in=review_in
    )
    return BaseResponse.success(data=TaskSubmissionOut.from_attributes(submission), message="审核评阅成功")

@router.get("/{task_id}", response_model=BaseResponse[Dict[str, Any]], summary="获取任务详情（包含分配与提交状态）")
async def get_task_details(
    task_id: UUID = Path(..., description="任务ID"),
    current_user: User = Depends(require_staff),
    db: AsyncSession = Depends(get_db)
):
    from app.core.exceptions import NotFoundError
    details = await TaskService.get_task_details(db, task_id=task_id)
    if not details:
        raise NotFoundError("任务不存在")
    return BaseResponse.success(data=details, message="获取成功")

