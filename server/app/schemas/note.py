from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, Field

class NoteBase(BaseModel):
    title: Optional[str] = Field(None, max_length=255, description="便签标题")
    content: str = Field(..., description="便签正文内容")
    color: Optional[str] = Field(None, max_length=100, description="低饱和度背景颜色样式")
    category: Optional[str] = Field(None, max_length=100, description="分类")
    is_pinned: bool = Field(False, description="是否置顶")
    sort_order: int = Field(0, description="排序权重")

class NoteCreate(NoteBase):
    pass

class NoteUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=255)
    content: Optional[str] = None
    color: Optional[str] = Field(None, max_length=100)
    category: Optional[str] = Field(None, max_length=100)
    is_pinned: Optional[bool] = None
    sort_order: Optional[int] = None

class NoteOut(NoteBase):
    id: UUID
    user_id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
