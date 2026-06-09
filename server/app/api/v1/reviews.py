from typing import List, Optional
from uuid import UUID
from datetime import date
from fastapi import APIRouter, Depends, Query, Path, Body
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.common import BaseResponse, PageData
from app.schemas.student_memory import DailyReviewOut, DailyReviewListOut, DailyReviewGenerateReq
from app.services.memory_service import MemoryService
from app.api.deps import get_current_user
from app.models.user import User
from app.core.exceptions import PermissionDenied, ValidationError
from app.services.access_control import AccessControlService

router = APIRouter()


async def resolve_review_student_id(
    db: AsyncSession,
    current_user: User,
    requested_student_id: Optional[UUID],
) -> UUID:
    if "student" in current_user.role_codes:
        if requested_student_id and requested_student_id != current_user.id:
            raise PermissionDenied("学生只能生成自己的每日复盘与 Memory")
        return current_user.id

    if not any(r in current_user.role_codes for r in ["teacher", "admin"]):
        raise PermissionDenied("无权操作每日复盘报告")

    if not requested_student_id:
        raise ValidationError("老师/管理员触发复盘时必须指定学生ID", code="STUDENT_ID_REQUIRED")

    await AccessControlService.ensure_can_access_student(db, current_user, requested_student_id)
    return requested_student_id

@router.get("/{date_val}", response_model=BaseResponse[DailyReviewOut], summary="获取每日复盘报告")
async def get_daily_review(
    date_val: date = Path(..., description="复盘日期, 格式 YYYY-MM-DD"),
    student_id: Optional[UUID] = Query(None, description="学生ID（老师/管理员必填，学生默认为自己）"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    target_student_id = await resolve_review_student_id(db, current_user, student_id)
    
    review = await MemoryService.get_daily_review(db, target_student_id, date_val)
    
    # Map raw model structure to out schema
    highlights = []
    concerns = []
    suggestions = []
    
    # We parse highlights and suggestions from markdown summary or stats
    # For MVP, retrieve from stats or use default parse split from review.summary
    if review.summary:
        lines = review.summary.split("\n")
        current_section = None
        for line in lines:
            line_strip = line.strip()
            if "高光" in line or "Highlights" in line or "亮点" in line:
                current_section = "highlights"
            elif "关注点" in line or "Concerns" in line or "薄弱" in line:
                current_section = "concerns"
            elif "建议" in line or "Suggestions" in line:
                current_section = "suggestions"
            elif line_strip.startswith("-") or line_strip.startswith("*") or (len(line_strip) > 2 and line_strip[0].isdigit() and line_strip[1] in [".", "、"]):
                cleaned = line_strip.lstrip("-*0123456789.、 ")
                if current_section == "highlights":
                    highlights.append(cleaned)
                elif current_section == "concerns":
                    concerns.append(cleaned)
                elif current_section == "suggestions":
                    suggestions.append(cleaned)
                    
    if not concerns and review.task_stats and review.task_stats.get("todos_created", 0) > review.task_stats.get("todos_completed", 0):
        concerns = ["今日有待办事项未全部完成，请注意跟进进度"]

    study_time = review.study_stats.get("study_time_minutes", 0) if review.study_stats else 0

    data = DailyReviewOut(
        id=review.id,
        student_id=review.user_id,
        date=review.review_date,
        summary=review.summary,
        study_time_minutes=study_time,
        metrics=review.behavior_stats,
        highlights=highlights,
        concerns=concerns,
        suggestions=suggestions,
        new_memories=review.new_memories or [],
        generated_at=review.created_at
    )
    return BaseResponse.success(data=data, message="获取成功")

@router.get("", response_model=BaseResponse[PageData[DailyReviewListOut]], summary="获取复盘报告列表")
async def list_daily_reviews(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页条数"),
    student_id: Optional[UUID] = Query(None, description="学生ID（老师/管理员查看时必填，学生默认为自己）"),
    start_date: Optional[date] = Query(None, description="起始日期"),
    end_date: Optional[date] = Query(None, description="结束日期"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    target_student_id = await resolve_review_student_id(db, current_user, student_id)
    
    reviews, total = await MemoryService.list_daily_reviews(
        db, target_student_id, page, page_size, start_date, end_date
    )
    
    list_items = []
    for r in reviews:
        summary_preview = ""
        if r.summary:
            # strip markdown headers/list symbols for preview
            summary_preview = r.summary.replace("#", "").replace("-", "").replace("\n", " ")[:100] + "..."
            
        study_time = r.study_stats.get("study_time_minutes", 0) if r.study_stats else 0
        
        concern_count = 0
        if r.task_stats:
            todos_pending = r.task_stats.get("todos_created", 0) - r.task_stats.get("todos_completed", 0)
            if todos_pending > 0:
                concern_count += 1
                
        list_items.append(
            DailyReviewListOut(
                id=r.id,
                date=r.review_date,
                study_time_minutes=study_time,
                summary_preview=summary_preview,
                concern_count=concern_count,
                generated_at=r.created_at
            )
        )
        
    page_data = PageData.create(items=list_items, total=total, page=page, page_size=page_size)
    return BaseResponse.success(data=page_data, message="获取成功")

@router.post("/generate", response_model=BaseResponse[DailyReviewOut], summary="手动触发复盘生成")
async def generate_daily_review_endpoint(
    req_body: DailyReviewGenerateReq = Body(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    target_student_id = await resolve_review_student_id(db, current_user, req_body.student_id)
    review = await MemoryService.generate_daily_review(db, target_student_id, req_body.date)
    study_time = review.study_stats.get("study_time_minutes", 0) if review.study_stats else 0
    data = DailyReviewOut(
        id=review.id,
        student_id=review.user_id,
        date=review.review_date,
        summary=review.summary,
        study_time_minutes=study_time,
        metrics=review.behavior_stats,
        highlights=[],
        concerns=[],
        suggestions=[],
        new_memories=review.new_memories or [],
        generated_at=review.created_at,
    )
    return BaseResponse.success(data=data, message="复盘与 Memory 已同步生成")
