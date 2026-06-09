from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, Query, Path
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.schemas.common import BaseResponse
from app.schemas.notification import NotificationOut
from app.services.notification_service import NotificationService
from app.api.deps import get_current_user
from app.models.user import User

router = APIRouter()

@router.get("/", response_model=BaseResponse[List[NotificationOut]], summary="获取通知列表")
async def list_notifications(
    unread_only: bool = Query(False, description="仅获取未读通知"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    notifications = await NotificationService.list_notifications(
        db, user_id=current_user.id, unread_only=unread_only
    )
    return BaseResponse.success(
        data=[NotificationOut.model_validate(n) for n in notifications],
        message="获取成功"
    )

@router.post("/{notification_id}/read", response_model=BaseResponse[NotificationOut], summary="标记通知为已读")
async def mark_notification_read(
    notification_id: UUID = Path(..., description="通知ID"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    notification = await NotificationService.mark_read(
        db, notification_id=notification_id, user_id=current_user.id
    )
    return BaseResponse.success(
        data=NotificationOut.model_validate(notification),
        message="标记成功"
    )

@router.post("/read-all", response_model=BaseResponse[bool], summary="标记所有通知为已读")
async def mark_all_notifications_read(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    success = await NotificationService.mark_all_read(db, user_id=current_user.id)
    return BaseResponse.success(data=success, message="全部标记已读成功")
