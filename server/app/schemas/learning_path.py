from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class ClassCreate(BaseModel):
    name: str = Field(..., max_length=120)
    description: Optional[str] = None
    grade: Optional[str] = None
    subject: Optional[str] = None
    student_ids: List[UUID] = Field(default_factory=list)


class ClassMemberOut(BaseModel):
    id: UUID
    user_id: UUID
    username: Optional[str] = None
    nickname: Optional[str] = None
    status: str
    joined_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ClassOut(BaseModel):
    id: UUID
    teacher_id: UUID
    name: str
    description: Optional[str] = None
    grade: Optional[str] = None
    subject: Optional[str] = None
    status: str
    created_at: datetime
    member_count: int = 0
    members: List[ClassMemberOut] = Field(default_factory=list)

    class Config:
        from_attributes = True


class LearningPathResourceIn(BaseModel):
    resource_type: str = Field(..., description="bilibili, file, link, text")
    title: Optional[str] = None
    url: Optional[str] = None
    bv_id: Optional[str] = None
    file_id: Optional[UUID] = None
    metadata: Optional[Dict[str, Any]] = None


class LearningPathResourceOut(LearningPathResourceIn):
    id: UUID
    task_id: UUID
    node_id: Optional[UUID] = None

    class Config:
        from_attributes = True


class LearningPathNodeIn(BaseModel):
    key: Optional[str] = None
    title: str
    description: Optional[str] = None
    node_type: str = Field("learning", description="learning, video, reading, practice, submission, checkpoint")
    order_index: int = 0
    estimated_minutes: int = 45
    required: bool = True
    config: Optional[Dict[str, Any]] = None
    resources: List[LearningPathResourceIn] = Field(default_factory=list)


class LearningPathNodeOut(BaseModel):
    id: UUID
    task_id: UUID
    stage_id: Optional[UUID] = None
    key: str
    title: str
    description: Optional[str] = None
    node_type: str
    order_index: int
    estimated_minutes: int
    required: bool
    config: Optional[Dict[str, Any]] = None
    resources: List[LearningPathResourceOut] = Field(default_factory=list)
    progress: Optional[Dict[str, Any]] = None

    class Config:
        from_attributes = True


class LearningPathStageIn(BaseModel):
    title: str
    description: Optional[str] = None
    order_index: int = 0


class LearningPathStageOut(BaseModel):
    id: UUID
    task_id: UUID
    title: str
    description: Optional[str] = None
    order_index: int

    class Config:
        from_attributes = True


class LearningPathEdgeIn(BaseModel):
    source_key: str
    target_key: str


class LearningPathEdgeOut(BaseModel):
    id: UUID
    task_id: UUID
    source_node_id: Optional[UUID] = None
    target_node_id: Optional[UUID] = None
    source_key: str
    target_key: str

    class Config:
        from_attributes = True


class LearningPathGenerateReq(BaseModel):
    goal: str = Field(..., min_length=2)
    planning_text: str = Field(..., min_length=2)


class LearningPathPlanOut(BaseModel):
    stages: List[LearningPathStageIn]
    nodes: List[LearningPathNodeIn]
    edges: List[LearningPathEdgeIn]
    resources: List[LearningPathResourceIn] = Field(default_factory=list)
    summary: str


class LearningPathCreate(BaseModel):
    title: str = Field(..., max_length=255)
    goal: str
    planning_text: Optional[str] = None
    description: Optional[str] = None
    class_id: Optional[UUID] = None
    assignee_ids: List[UUID] = Field(default_factory=list)
    due_date: Optional[datetime] = None
    publish: bool = False
    nodes: Optional[List[LearningPathNodeIn]] = None
    stages: Optional[List[LearningPathStageIn]] = None
    edges: Optional[List[LearningPathEdgeIn]] = None


class LearningPathUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=255)
    goal: Optional[str] = None
    planning_text: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    due_date: Optional[datetime] = None
    nodes: Optional[List[LearningPathNodeIn]] = None
    stages: Optional[List[LearningPathStageIn]] = None
    edges: Optional[List[LearningPathEdgeIn]] = None


class LearningPathTaskOut(BaseModel):
    id: UUID
    creator_id: UUID
    class_id: Optional[UUID] = None
    title: str
    goal: str
    planning_text: Optional[str] = None
    description: Optional[str] = None
    status: str
    due_date: Optional[datetime] = None
    published_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    assignee_count: int = 0
    avg_progress: float = 0.0

    class Config:
        from_attributes = True


class LearningPathDetailOut(BaseModel):
    task: LearningPathTaskOut
    stages: List[LearningPathStageOut]
    nodes: List[LearningPathNodeOut]
    edges: List[LearningPathEdgeOut]
    assignees: List[Dict[str, Any]] = Field(default_factory=list)
    submissions: List[Dict[str, Any]] = Field(default_factory=list)


class LearningNodeSubmitReq(BaseModel):
    content: Optional[str] = None
    attachment_ids: List[UUID] = Field(default_factory=list)
    mark_complete: bool = True


class LearningNodeReviewReq(BaseModel):
    review_status: str = Field("approved", description="approved, rejected, revise")
    score: Optional[float] = Field(None, ge=0, le=100)
    feedback: Optional[str] = None
    follow_up: Optional[str] = None
    reopen_until: Optional[datetime] = None


class InsightEvidenceOut(BaseModel):
    source_type: str
    source_id: Optional[UUID] = None
    student_id: Optional[UUID] = None
    student_name: Optional[str] = None
    content: str
    occurred_at: Optional[datetime] = None


class InsightActionOut(BaseModel):
    action_type: str
    label: str
    payload: Dict[str, Any] = Field(default_factory=dict)


class LearningInsightOut(BaseModel):
    id: UUID
    scope: str
    class_id: Optional[UUID] = None
    student_id: Optional[UUID] = None
    teacher_id: Optional[UUID] = None
    title: str
    insight_type: str
    severity: str
    summary: str
    affected_student_ids: List[UUID] = Field(default_factory=list)
    evidence: List[InsightEvidenceOut] = Field(default_factory=list)
    suggested_actions: List[InsightActionOut] = Field(default_factory=list)
    status: str
    source: str
    source_fingerprint: Optional[str] = None
    generated_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class LearningInsightStatusUpdate(BaseModel):
    status: str = Field(..., description="new, acknowledged, resolved, dismissed")


class ClassOverviewOut(BaseModel):
    class_info: ClassOut
    metrics: Dict[str, Any]
    trend: List[Dict[str, Any]]
    memory_summary: Dict[str, Any]
    insights: List[LearningInsightOut] = Field(default_factory=list)
    attention_students: List[Dict[str, Any]]
    recent_paths: List[LearningPathTaskOut]


class StudentGrowthOverviewOut(BaseModel):
    student_id: UUID
    profile: Dict[str, Any]
    metrics: Dict[str, Any]
    trend: List[Dict[str, Any]]
    learning_paths: List[LearningPathTaskOut]
    memory_cards: List[Dict[str, Any]]
    parent_summary: str
