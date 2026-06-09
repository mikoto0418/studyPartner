from typing import List
from uuid import UUID
from fastapi import APIRouter, Depends, Body, Path
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.schemas.common import BaseResponse
from app.schemas.announcement import AnnouncementOut, AnnouncementCreate
from app.services.announcement_service import AnnouncementService
from app.api.deps import get_current_user, require_staff
from app.models.user import User

router = APIRouter()

@router.get("/", response_model=BaseResponse[List[AnnouncementOut]], summary="获取公告列表")
async def list_announcements(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    role_codes = current_user.role_codes
    announcements = await AnnouncementService.list_announcements_for_user(
        db, user_id=current_user.id, role_codes=role_codes
    )
    return BaseResponse.success(
        data=[AnnouncementOut.model_validate(a) for a in announcements],
        message="获取成功"
    )

@router.post("/", response_model=BaseResponse[AnnouncementOut], summary="发布新公告")
async def create_announcement(
    announcement_in: AnnouncementCreate = Body(...),
    current_user: User = Depends(require_staff),
    db: AsyncSession = Depends(get_db)
):
    announcement = await AnnouncementService.create_announcement(
        db, creator_id=current_user.id, announcement_in=announcement_in
    )
    return BaseResponse.success(
        data=AnnouncementOut.model_validate(announcement),
        message="发布成功"
    )

@router.post("/{announcement_id}/read", response_model=BaseResponse[bool], summary="标记公告为已读")
async def mark_announcement_as_read(
    announcement_id: UUID = Path(..., description="公告ID"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    await AnnouncementService.mark_read(db, announcement_id=announcement_id, user_id=current_user.id)
    return BaseResponse.success(data=True, message="标记成功")
