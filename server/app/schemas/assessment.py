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
    # 编程题：语言三选一；test_cases 里 is_sample=true 的会下发学生，其余仅判题
    language: Optional[str] = None
    test_cases: Optional[List[dict]] = None
    starter_code: Optional[str] = None
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
    language: Optional[str] = None
    test_cases: Optional[List[dict]] = None
    starter_code: Optional[str] = None
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
    # 开考后限时，单位分钟。与 due_at 同时存在时，先到的那个收卷
    time_limit_minutes: Optional[int] = Field(default=None, ge=1, le=1440)
    # 主观题批阅倾向，随发布一并保存；{mode: lenient/standard/strict, extra: str}
    grading_preference: Optional[dict] = None


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
    grading_preference: Optional[dict] = None
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
    # 编程题：语言、起始代码、以及只有样例的测试用例（隐藏用例不下发）
    language: Optional[str] = None
    starter_code: Optional[str] = None
    sample_cases: Optional[List[dict]] = None

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

    @field_validator("sample_cases", mode="before")
    @classmethod
    def _only_samples(cls, value):
        """只放样例用例。隐藏用例一旦下发，学生直接照着输出打表就能满分。"""
        if not value or not isinstance(value, list):
            return None
        out = [
            {"input": c.get("input", ""), "expected_output": c.get("expected_output", "")}
            for c in value
            if isinstance(c, dict) and c.get("is_sample")
        ]
        return out or None


class StudentPaperOut(BaseModel):
    id: UUID
    title: str
    description: Optional[str] = None
    question_count: int
    total_score: Optional[float] = None
    published_at: Optional[datetime] = None
    due_at: Optional[datetime] = None
    time_limit_minutes: Optional[int] = None
    attempt_id: Optional[UUID] = None
    attempt_status: Optional[str] = None
    attempt_score: Optional[float] = None


class StudentReviewQuestionOut(BaseModel):
    question_id: UUID
    order_index: int
    question_type: str
    stem: str
    stem_images: Optional[List[dict]] = None
    options: Optional[List[dict]] = None
    max_score: Optional[float] = None
    student_answer: Optional[Any] = None
    score: Optional[float] = None
    graded: bool = False
    is_correct: Optional[bool] = None
    reference_answer: Optional[Any] = None
    analysis: Optional[str] = None
    language: Optional[str] = None
    sample_cases: Optional[List[dict]] = None
    # 编程题只回通过数，不回隐藏用例内容
    judge_summary: Optional[dict] = None


class StudentReviewOut(BaseModel):
    """交卷后的成绩回顾。score 仅在全部批完后才有；客观题小计始终给出。"""

    paper: Dict[str, Any]
    attempt: Dict[str, Any]
    questions: List[StudentReviewQuestionOut] = Field(default_factory=list)


class StudentAttemptOut(BaseModel):
    id: UUID
    paper_id: UUID
    status: str
    started_at: Optional[datetime] = None
    submitted_at: Optional[datetime] = None
    score: Optional[float] = None
    duration_seconds: Optional[int] = None
    # 本次作答的实际截止时刻：整卷截止与开考限时中较早的那个
    answer_deadline: Optional[datetime] = None
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
    # 编程题：语言、判题通过数与逐用例明细（教师可见隐藏用例）
    language: Optional[str] = None
    judge_summary: Optional[dict] = None
    judge_detail: Optional[dict] = None
    # AI 预批阅建议：教师确认前只是参考值，不写进 score
    ai_suggested_score: Optional[float] = None
    ai_comment: Optional[str] = None
    ai_graded_at: Optional[datetime] = None


class AIGradeReq(BaseModel):
    """AI 预批阅请求。question_ids 为空表示批本卷全部主观题。"""

    question_ids: List[UUID] = Field(default_factory=list, max_length=200)
    overwrite: bool = False


class AIGradeItemOut(BaseModel):
    question_id: UUID
    suggested_score: Optional[float] = None
    max_score: Optional[float] = None
    comment: str = ""
    error: Optional[str] = None


class AIGradeOut(BaseModel):
    graded: int = 0
    failed: int = 0
    # 已有人工分或已有建议、且本次未要求覆盖的题
    skipped: int = 0
    items: List[AIGradeItemOut] = Field(default_factory=list)


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


class AttemptInsightsOut(BaseModel):
    """单次作答的按题行为画像。"""

    attempt: Dict[str, Any]
    questions: List[Dict[str, Any]] = Field(default_factory=list)


class StudentExamHistoryOut(BaseModel):
    """某学生在当前教师名下的历次考试。"""

    student: Dict[str, Any]
    attempts: List[Dict[str, Any]] = Field(default_factory=list)


class ClassExamAnalyticsOut(BaseModel):
    """班级维度的考试概况。"""

    class_info: Dict[str, Any]
    summary: Dict[str, Any]
    papers: List[Dict[str, Any]] = Field(default_factory=list)
    students: List[Dict[str, Any]] = Field(default_factory=list)