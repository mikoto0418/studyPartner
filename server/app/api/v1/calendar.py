from datetime import datetime
from typing import List
from uuid import UUID
from fastapi import APIRouter, Depends, Query, Path, Body
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.schemas.common import BaseResponse
from app.schemas.calendar_event import CalendarEventOut, CalendarEventCreate, CalendarEventUpdate
from app.services.calendar_service import CalendarService
from app.api.deps import get_current_user
from app.models.user import User

router = APIRouter()

@router.get("/", response_model=BaseResponse[List[CalendarEventOut]], summary="获取日程事件列表")
async def list_events(
    start_time: datetime = Query(..., description="开始时间范围 (ISO格式)"),
    end_time: datetime = Query(..., description="结束时间范围 (ISO格式)"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    events = await CalendarService.list_events(
        db, user_id=current_user.id, start_time=start_time, end_time=end_time
    )
    return BaseResponse.success(
        data=[CalendarEventOut.model_validate(e) for e in events],
        message="获取成功"
    )

@router.post("/", response_model=BaseResponse[CalendarEventOut], summary="创建日程事件")
async def create_event(
    event_in: CalendarEventCreate = Body(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    event = await CalendarService.create_event(db, creator=current_user, event_in=event_in)
    return BaseResponse.success(
        data=CalendarEventOut.model_validate(event),
        message="创建成功"
    )

@router.put("/{event_id}", response_model=BaseResponse[CalendarEventOut], summary="更新日程事件")
async def update_event(
    event_id: UUID = Path(..., description="日程ID"),
    event_in: CalendarEventUpdate = Body(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    event = await CalendarService.update_event(
        db, event_id=event_id, user_id=current_user.id, event_in=event_in
    )
    return BaseResponse.success(
        data=CalendarEventOut.model_validate(event),
        message="更新成功"
    )

@router.delete("/{event_id}", response_model=BaseResponse[bool], summary="删除日程事件")
async def delete_event(
    event_id: UUID = Path(..., description="日程ID"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    await CalendarService.delete_event(db, event_id=event_id, user_id=current_user.id)
    return BaseResponse.success(data=True, message="删除成功")
