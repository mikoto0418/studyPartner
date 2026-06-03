from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, Field

class NotificationBase(BaseModel):
    title: str = Field(..., max_length=255, description="通知标题")
    content: str = Field(..., description="通知正文内容")
    notification_type: str = Field("system", description="通知类型")
    link_url: Optional[str] = Field(None, max_length=255, description="跳转链接")

class NotificationOut(NotificationBase):
    id: UUID
    user_id: UUID
    read_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True
