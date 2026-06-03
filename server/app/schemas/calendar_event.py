from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, Field

class CalendarEventBase(BaseModel):
    title: str = Field(..., max_length=255, description="日程标题")
    description: Optional[str] = Field(None, description="日程详情描述")
    event_type: str = Field("personal", description="日程类型: personal, task, countdown, teacher_assigned")
    status: str = Field("planned", description="日程状态: planned, in_progress, completed, cancelled")
    start_time: datetime = Field(..., description="开始时间")
    end_time: datetime = Field(..., description="结束时间")
    all_day: bool = Field(False, description="是否全天日程")
    color: Optional[str] = Field(None, max_length=50, description="日程标签颜色")
    related_task_id: Optional[UUID] = Field(None, description="关联的任务ID")
    related_countdown_id: Optional[UUID] = Field(None, description="关联的倒数日ID")

class CalendarEventCreate(CalendarEventBase):
    user_id: Optional[UUID] = Field(None, description="特定被指派的用户ID (教师给学生制定时有效，学生自用不需传)")

class CalendarEventUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    event_type: Optional[str] = None
    status: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    all_day: Optional[bool] = None
    color: Optional[str] = Field(None, max_length=50)
    related_task_id: Optional[UUID] = None
    related_countdown_id: Optional[UUID] = None

class CalendarEventOut(CalendarEventBase):
    id: UUID
    user_id: UUID
    created_by: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
