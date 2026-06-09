from datetime import datetime, date as Date
from typing import Optional, List, Any
from uuid import UUID
from pydantic import BaseModel, Field

class StudentMemoryBase(BaseModel):
    memory_type: str = Field(..., description="Memory 类型: short_term, long_term")
    category: str = Field("other", description="分类: learning_preference, study_habit, interest_area, weakness, goal, other")
    content: str = Field(..., description="Memory 内容")
    evidence: Optional[str] = Field(None, description="证据/支撑行为")
    confidence: float = Field(0.5, description="置信度 (0.0-1.0)")
    status: str = Field("active", description="状态: active, superseded, archived, deleted")
    source_review_id: Optional[UUID] = Field(None, description="源复盘记录ID")
    context_metadata: Optional[Any] = Field(None, description="上下文元数据")
    version: int = Field(1, description="版本号")
    superseded_by: Optional[UUID] = Field(None, description="被哪个更替了")
    expires_at: Optional[datetime] = Field(None, description="过期时间")

class StudentMemoryOut(StudentMemoryBase):
    id: UUID
    user_id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class StudentMemoryGroupedOut(BaseModel):
    student_id: UUID
    short_term: List[StudentMemoryOut] = []
    long_term: List[StudentMemoryOut] = []
    last_updated_at: Optional[datetime] = None

class MemoryDeleteReq(BaseModel):
    reason: Optional[str] = Field(None, description="申请删除原因")

class MemoryUpdateLogOut(BaseModel):
    id: UUID
    action: str = Field(..., description="操作类型: create, update, delete")
    memory_id: UUID
    content: str
    layer: str = Field(..., description="short_term, long_term")
    confidence: float
    source: str = Field(..., description="来源, 如 daily_review, manual")
    review_date: Optional[Date] = None
    created_at: datetime

class DailyReviewBase(BaseModel):
    review_date: Date
    summary: Optional[str] = None
    study_stats: Optional[Any] = None
    task_stats: Optional[Any] = None
    behavior_stats: Optional[Any] = None
    ai_suggestion: Optional[str] = None
    new_memories: Optional[List[Any]] = None
    updated_memories: Optional[List[Any]] = None
    model_name: Optional[str] = None
    token_count: Optional[int] = None
    status: str = Field("pending", description="状态")
    error_message: Optional[str] = None

class DailyReviewOut(BaseModel):
    id: UUID
    student_id: UUID
    date: Date
    summary: Optional[str] = None
    study_time_minutes: int = 0
    metrics: Optional[Any] = None
    highlights: List[str] = []
    concerns: List[str] = []
    suggestions: List[str] = []
    new_memories: List[Any] = []
    generated_at: datetime

    class Config:
        from_attributes = True

class DailyReviewListOut(BaseModel):
    id: UUID
    date: Date
    study_time_minutes: int = 0
    summary_preview: Optional[str] = None
    concern_count: int = 0
    generated_at: datetime

class DailyReviewGenerateReq(BaseModel):
    student_id: Optional[UUID] = Field(None, description="学生ID。学生端可省略，默认生成自己的复盘；老师/管理员触发时必填。")
    date: Date = Field(..., description="需要复盘的日期, 格式 YYYY-MM-DD")
