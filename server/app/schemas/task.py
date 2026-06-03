from datetime import datetime
from typing import Optional, List
from uuid import UUID
from pydantic import BaseModel, Field

class TaskBase(BaseModel):
    title: str = Field(..., max_length=255, description="任务标题")
    description: Optional[str] = Field(None, description="任务详情描述")
    priority: str = Field("medium", description="优先级: low, medium, high, urgent")
    status: str = Field("in_progress", description="状态")
    start_date: Optional[datetime] = Field(None, description="起始时间")
    due_date: Optional[datetime] = Field(None, description="截止时间")
    attachment_ids: Optional[List[UUID]] = Field(default=None, description="附件文件ID列表")

class TaskCreate(TaskBase):
    assignee_ids: List[UUID] = Field(..., description="要指派的学生用户ID列表")

class TaskUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    priority: Optional[str] = None
    status: Optional[str] = None
    start_date: Optional[datetime] = None
    due_date: Optional[datetime] = None
    attachment_ids: Optional[List[UUID]] = None

class TaskOut(TaskBase):
    id: UUID
    creator_id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class TaskAssigneeOut(BaseModel):
    id: UUID
    task_id: UUID
    user_id: UUID
    status: str
    assigned_at: Optional[datetime]
    completed_at: Optional[datetime]

    class Config:
        from_attributes = True

class TaskSubmissionCreate(BaseModel):
    content: Optional[str] = Field(None, description="提交说明")
    attachment_ids: Optional[List[UUID]] = Field(default=[], description="提交的附件文件ID列表")

class TaskSubmissionReview(BaseModel):
    status: str = Field(..., description="审核状态: completed, rejected")
    feedback: Optional[str] = Field(None, description="教师评语/反馈意见")

class TaskSubmissionOut(BaseModel):
    id: UUID
    task_id: UUID
    assignee_id: UUID
    user_id: UUID
    content: Optional[str]
    attachment_ids: Optional[List[UUID]]
    feedback: Optional[str]
    reviewed_by: Optional[UUID]
    reviewed_at: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True
