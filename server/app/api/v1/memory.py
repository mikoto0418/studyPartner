from typing import List, Optional
from uuid import UUID
from datetime import date
from fastapi import APIRouter, Depends, Query, Path, Body
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.common import BaseResponse, PageData
from app.schemas.student_memory import StudentMemoryOut, StudentMemoryGroupedOut, MemoryUpdateLogOut, MemoryDeleteReq
from app.services.memory_service import MemoryService
from app.api.deps import get_current_user
from app.models.user import User
from app.core.exceptions import PermissionDenied

router = APIRouter()

def verify_student_or_staff(current_user: User, student_id: UUID):
    user_roles = [role.code for role in current_user.roles]
    if "student" in user_roles and current_user.id != student_id:
        raise PermissionDenied("权限不足，学生只能查看或操作自己的 Memory")
    if not any(r in user_roles for r in ["student", "teacher", "admin"]):
        raise PermissionDenied("无权查看该学生 Memory 信息")

@router.get("/{student_id}", response_model=BaseResponse[StudentMemoryGroupedOut], summary="获取学生 Memory")
async def get_student_memory(
    student_id: UUID = Path(..., description="学生ID"),
    layer: str = Query("all", description="Memory 层级：short_term, long_term, all"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    verify_student_or_staff(current_user, student_id)
    memories, last_updated = await MemoryService.get_student_memories(db, student_id, layer)
    
    short_term_outs = [StudentMemoryOut.from_attributes(m) for m in memories if m.memory_type == "short_term"]
    long_term_outs = [StudentMemoryOut.from_attributes(m) for m in memories if m.memory_type == "long_term"]
    
    data = StudentMemoryGroupedOut(
        student_id=student_id,
        short_term=short_term_outs,
        long_term=long_term_outs,
        last_updated_at=last_updated
    )
    return BaseResponse.success(data=data, message="获取成功")

@router.delete("/{student_id}/{memory_id}", response_model=BaseResponse[None], summary="申请删除/直接删除 Memory 条目")
async def delete_student_memory(
    student_id: UUID = Path(..., description="学生ID"),
    memory_id: UUID = Path(..., description="Memory ID"),
    req_body: Optional[MemoryDeleteReq] = Body(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    user_roles = [role.code for role in current_user.roles]
    if "student" in user_roles and current_user.id != student_id:
        raise PermissionDenied("权限不足，学生只能删除自己的 Memory")
    if not any(r in user_roles for r in ["student", "admin"]):
        raise PermissionDenied("无权删除该 Memory 条目")
        
    await MemoryService.delete_student_memory(db, student_id, memory_id)
    return BaseResponse.success(data=None, message="Memory 条目已删除")

@router.get("/{student_id}/update-logs", response_model=BaseResponse[PageData[MemoryUpdateLogOut]], summary="获取 Memory 更新日志")
async def get_memory_update_logs(
    student_id: UUID = Path(..., description="学生ID"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页条数"),
    start_date: Optional[date] = Query(None, description="起始日期"),
    end_date: Optional[date] = Query(None, description="结束日期"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    user_roles = [role.code for role in current_user.roles]
    if "student" in user_roles and current_user.id != student_id:
        raise PermissionDenied("权限不足，学生只能查看自己的 Memory 更新日志")
    if not any(r in user_roles for r in ["student", "admin"]):
        raise PermissionDenied("无权查看该更新日志")
        
    logs, total = await MemoryService.get_memory_update_logs(
        db, student_id, page, page_size, start_date, end_date
    )
    
    log_outs = [
        MemoryUpdateLogOut(
            id=log["id"],
            action=log["action"],
            memory_id=log["memory_id"],
            content=log["content"],
            layer=log["layer"],
            confidence=log["confidence"],
            source=log["source"],
            review_date=log["review_date"],
            created_at=log["created_at"]
        )
        for log in logs
    ]
    
    page_data = PageData.create(items=log_outs, total=total, page=page, page_size=page_size)
    return BaseResponse.success(data=page_data, message="获取成功")
