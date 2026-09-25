from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class AssessmentPaperCreateReq(BaseModel):
    file_id: UUID
    title: str = Field(..., max_length=255)
    description: Optional[str] = None


class AssessmentQuestionIn(BaseModel):
    order_index: int = 0
    question_type: str
    stem: str
    stem_images: Optional[List[dict]] = None
    options: Optional[List[dict]] = None
    answer: Optional[Any] = None
    analysis: Optional[str] = None
    # 留空表示「未设置分值」，由教师在后续编辑页手动补；不能用 0 冒充
    score: Optional[float] = None
    difficulty: Optional[float] = None
    tags: Optional[List[str]] = None
    source_chunk: Optional[dict] = None


class AssessmentQuestionOut(BaseModel):
    id: UUID
    paper_id: UUID
    order_index: int
    question_type: str
    stem: str
    stem_images: Optional[List[dict]] = None
    options: Optional[List[dict]] = None
    answer: Optional[Any] = None
    analysis: Optional[str] = None
    score: Optional[float] = None
    difficulty: Optional[float] = None
    tags: Optional[List[str]] = None
    source_chunk: Optional[dict] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class QuestionsSaveReq(BaseModel):
    questions: List[AssessmentQuestionIn] = Field(default_factory=list)


class AssessmentPublishReq(BaseModel):
    publish_target: dict
    publish_at: Optional[datetime] = None
    due_at: Optional[datetime] = None


class ParseStatusOut(BaseModel):
    parse_status: str
    parse_progress: Optional[dict] = None
    parse_error: Optional[str] = None
    question_count: int
    total_score: Optional[float] = None


class AssessmentPaperOut(BaseModel):
    id: UUID
    title: str
    description: Optional[str] = None
    source_file_id: Optional[UUID] = None
    parse_status: str
    parse_progress: Optional[dict] = None
    parse_error: Optional[str] = None
    question_count: int
    total_score: Optional[float] = None
    publish_target: Optional[dict] = None
    publish_at: Optional[datetime] = None
    published_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class StudentQuestionOut(BaseModel):
    id: UUID
    order_index: int
    question_type: str
    stem: str
    stem_images: Optional[List[dict]] = None
    options: Optional[List[dict]] = None
    # 未设置分值时为 None，学生端应显示「未设置」而不是 0 分
    score: Optional[float] = None

    class Config:
        from_attributes = True

    @field_validator("options", mode="before")
    @classmethod
    def _strip_answer_marks(cls, value):
        """只放行 key/text，防止教师校对时写入的答案标记随题目下发。"""
        if not value:
            return value
        out = []
        for opt in value:
            if isinstance(opt, dict):
                out.append({k: opt[k] for k in ("key", "text") if k in opt})
            else:
                out.append(opt)
        return out


class StudentPaperOut(BaseModel):
    id: UUID
    title: str
    description: Optional[str] = None
    question_count: int
    total_score: Optional[float] = None
    published_at: Optional[datetime] = None
    due_at: Optional[datetime] = None
    attempt_id: Optional[UUID] = None
    attempt_status: Optional[str] = None
    attempt_score: Optional[float] = None


class StudentAttemptOut(BaseModel):
    id: UUID
    paper_id: UUID
    status: str
    started_at: Optional[datetime] = None
    submitted_at: Optional[datetime] = None
    score: Optional[float] = None
    duration_seconds: Optional[int] = None
    # 仅交卷响应会置位：超过截止宽限期时本次提交的答案未落库
    answers_ignored: bool = False

    class Config:
        from_attributes = True


class StudentAnswerIn(BaseModel):
    question_id: UUID
    answer: Optional[Any] = None


class StudentAnswersReq(BaseModel):
    # 一次提交最多覆盖 500 道题，防止超大 body 放大单请求的查库成本
    answers: List[StudentAnswerIn] = Field(default_factory=list, max_length=500)


class StudentAnswerOut(BaseModel):
    question_id: UUID
    answer: Optional[Any] = None


class StudentAnswersOut(BaseModel):
    attempt_id: Optional[UUID] = None
    status: Optional[str] = None
    answers: List[StudentAnswerOut] = Field(default_factory=list)


class BehaviorEventIn(BaseModel):
    event_type: str
    payload: Optional[dict] = None
    occurred_at: Optional[datetime] = None


class BehaviorBatchReq(BaseModel):
    session_id: str = Field(..., max_length=64)
    attempt_id: Optional[UUID] = None
    events: List[BehaviorEventIn] = Field(default_factory=list, max_length=200)


class AttemptAnswerOut(BaseModel):
    question_id: UUID
    order_index: int
    question_type: str
    stem: str
    options: Optional[List[dict]] = None
    reference_answer: Optional[Any] = None
    # 题目未设置分值时满分为未知，教师批改页据此禁用打分输入
    max_score: Optional[float] = None
    answer: Optional[Any] = None
    score: float = 0.0
    graded: bool = False
    is_correct: Optional[bool] = None


class GradeItemIn(BaseModel):
    question_id: UUID
    score: float = 0.0


class GradeAttemptReq(BaseModel):
    grades: List[GradeItemIn] = Field(default_factory=list)


class AttemptMonitorOut(BaseModel):
    id: UUID
    student_id: UUID
    student_name: str
    username: str
    status: str
    started_at: Optional[datetime] = None
    submitted_at: Optional[datetime] = None
    duration_seconds: Optional[int] = None
    score: Optional[float] = None
    suspicious: bool
    event_count: int
    flagged_count: int
    pending_grade_count: int = 0


class BehaviorEventOut(BaseModel):
    id: UUID
    event_type: str
    payload: Optional[dict] = None
    occurred_at: Optional[datetime] = None


class PaperAnalyticsOut(BaseModel):
    """教师端试卷分析聚合。字段结构由 service 组装，这里只做透传与文档化。"""

    paper: Dict[str, Any]
    overview: Dict[str, Any]
    score_distribution: List[Dict[str, Any]] = Field(default_factory=list)
    questions: List[Dict[str, Any]] = Field(default_factory=list)
    behavior_distribution: List[Dict[str, Any]] = Field(default_factory=list)
    suspicious_count: int = 0