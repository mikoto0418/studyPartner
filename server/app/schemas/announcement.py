from datetime import datetime
from typing import Optional, List
from uuid import UUID
from pydantic import BaseModel, Field

class AnnouncementBase(BaseModel):
    title: str = Field(..., max_length=255, description="公告标题")
    content: str = Field(..., description="公告正文")
    status: str = Field("published", description="状态: draft, published, expired, withdrawn")
    target_type: str = Field("all", description="针对人群: all, all_students, all_teachers, specific_users")
    is_pinned: bool = Field(False, description="是否置顶")
    publish_at: Optional[datetime] = Field(None, description="发布时间")
    expire_at: Optional[datetime] = Field(None, description="失效时间")

class AnnouncementCreate(AnnouncementBase):
    receiver_ids: Optional[List[UUID]] = Field(default=[], description="特定接收人ID列表 (当target_type为specific_users时有效)")

class AnnouncementUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=255)
    content: Optional[str] = None
    status: Optional[str] = None
    target_type: Optional[str] = None
    is_pinned: Optional[bool] = None
    publish_at: Optional[datetime] = None
    expire_at: Optional[datetime] = None
    receiver_ids: Optional[List[UUID]] = None

class AnnouncementOut(AnnouncementBase):
    id: UUID
    creator_id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
