from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, Field

class TodoBase(BaseModel):
    title: str = Field(..., max_length=255, description="待办标题")
    description: Optional[str] = Field(None, description="详情描述")
    priority: str = Field("medium", description="优先级: low, medium, high, urgent")
    status: str = Field("pending", description="状态: pending, completed, cancelled")
    category: Optional[str] = Field(None, max_length=100, description="分类")
    due_date: Optional[datetime] = Field(None, description="截止时间")
    sort_order: int = Field(0, description="排序权重")

class TodoCreate(TodoBase):
    pass

class TodoUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    priority: Optional[str] = None
    status: Optional[str] = None
    category: Optional[str] = Field(None, max_length=100)
    due_date: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    sort_order: Optional[int] = None

class TodoOut(TodoBase):
    id: UUID
    user_id: UUID
    completed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
