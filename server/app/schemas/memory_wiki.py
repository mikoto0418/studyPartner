from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class MemoryPageBase(BaseModel):
    slug: str = Field(..., description="页面 slug，用户内唯一")
    page_type: str = Field("concept", description="concept/entity/pattern/goal/weakness/event/relationship")
    title: str = Field(..., description="页面标题")
    summary: Optional[str] = Field(None, description="一句话摘要")
    body: Optional[str] = Field(None, description="Markdown 正文")
    category: str = Field("other", description="旧分类兼容")
    tags: Optional[List[str]] = Field(None, description="标签")
    confidence: float = Field(0.5, description="置信度 0~1")
    expires_at: Optional[datetime] = Field(None, description="过期时间")
    meta: Optional[Dict[str, Any]] = Field(None, description="页面附加元数据")


class MemoryPageCreate(MemoryPageBase):
    pass


class MemoryPageUpdate(BaseModel):
    slug: Optional[str] = Field(None)
    page_type: Optional[str] = Field(None)
    title: Optional[str] = Field(None)
    summary: Optional[str] = Field(None)
    body: Optional[str] = Field(None)
    category: Optional[str] = Field(None)
    tags: Optional[List[str]] = Field(None)
    confidence: Optional[float] = Field(None, ge=0, le=1)
    expires_at: Optional[datetime] = Field(None)
    meta: Optional[Dict[str, Any]] = Field(None)


class MemoryPageOut(MemoryPageBase):
    id: UUID
    user_id: UUID
    status: str
    version: int
    source_review_id: Optional[UUID] = None
    last_reviewed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class MemoryPageDetailOut(MemoryPageOut):
    sources: List[Dict[str, Any]] = Field(default_factory=list)
    outbound_links: List[Dict[str, Any]] = Field(default_factory=list)
    inbound_links: List[Dict[str, Any]] = Field(default_factory=list)


class MemorySourceCreate(BaseModel):
    source_type: str
    source_id: Optional[str] = None
    occurred_at: Optional[datetime] = None
    snippet: Optional[str] = None
    confidence: float = Field(0.6, ge=0, le=1)
    meta: Optional[Dict[str, Any]] = None


class MemorySourceOut(MemorySourceCreate):
    id: UUID
    page_id: UUID
    user_id: UUID
    created_at: datetime

    class Config:
        from_attributes = True


class MemoryLinkCreate(BaseModel):
    to_page_id: UUID
    relation: str = Field("related_to", description="related_to/prerequisite_of/evidence_for/conflicts_with")
    strength: float = Field(0.5, ge=0, le=1)


class MemoryLinkOut(BaseModel):
    id: UUID
    user_id: UUID
    from_page_id: UUID
    to_page_id: UUID
    relation: str
    strength: float
    created_at: datetime

    class Config:
        from_attributes = True


class MemoryEventOut(BaseModel):
    id: UUID
    user_id: UUID
    page_id: Optional[UUID] = None
    action: str
    before: Optional[Dict[str, Any]] = None
    after: Optional[Dict[str, Any]] = None
    reason: Optional[str] = None
    operator: str
    review_id: Optional[UUID] = None
    meta: Optional[Dict[str, Any]] = None
    created_at: datetime

    class Config:
        from_attributes = True


class MemoryReviewTaskOut(BaseModel):
    id: UUID
    user_id: UUID
    page_id: Optional[UUID] = None
    task_type: str
    payload: Optional[Dict[str, Any]] = None
    status: str
    created_by: str
    handled_at: Optional[datetime] = None
    handled_by: Optional[UUID] = None
    handled_reason: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class MemorySearchReq(BaseModel):
    query: str = Field("", description="搜索关键词")
    top_k: int = Field(10, ge=1, le=50)
    page_type: Optional[str] = None
    category: Optional[str] = None
    status: str = Field("active")


class MemorySearchHit(BaseModel):
    page: MemoryPageOut
    score: float = Field(0, description="相关度分数")


class MemoryGraphNode(BaseModel):
    id: UUID
    title: str
    page_type: str
    category: str
    confidence: float
    status: str


class MemoryGraphEdge(BaseModel):
    id: UUID
    source: UUID
    target: UUID
    relation: str
    strength: float


class MemoryGraphOut(BaseModel):
    nodes: List[MemoryGraphNode] = Field(default_factory=list)
    edges: List[MemoryGraphEdge] = Field(default_factory=list)


class MemoryLintIssue(BaseModel):
    issue_type: str  # orphan, duplicate, no_evidence, expired, low_confidence
    page_id: UUID
    title: str
    message: str
    severity: str = Field("info", description="info/warning/error")


class MemoryLintOut(BaseModel):
    issues: List[MemoryLintIssue] = Field(default_factory=list)
    checked_pages: int = 0


class MemoryWikiStatsOut(BaseModel):
    total_pages: int
    active_pages: int
    source_count: int
    link_count: int
    review_task_count: int