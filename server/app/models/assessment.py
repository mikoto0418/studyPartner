from sqlalchemy import Column, String, Text, Float, Integer, Boolean, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from app.models.base import BaseModel


class AssessmentPaper(BaseModel):
    __tablename__ = "assessment_papers"

    creator_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    source_file_id = Column(UUID(as_uuid=True), ForeignKey("files.id", ondelete="SET NULL"), nullable=True, index=True)
    # pending, parsing, awaiting_review, published, failed
    parse_status = Column(String(30), default="pending", nullable=False)
    parse_progress = Column(JSONB, nullable=True)  # {stage, total, done, current}
    parse_error = Column(Text, nullable=True)
    question_count = Column(Integer, default=0, nullable=False)
    # 有题目未设置分值时整卷满分为未知，用 NULL 表达，不用 0 冒充
    total_score = Column(Float, nullable=True)
    publish_target = Column(JSONB, nullable=True)  # {type: class/group/student, ids, whitelist, blacklist}
    publish_at = Column(DateTime(timezone=True), nullable=True)  # 预约发布时间
    published_at = Column(DateTime(timezone=True), nullable=True)  # 实际发布时间
    # 教师对本卷主观题的批阅倾向：{mode: lenient/standard/strict, extra: 补充说明}
    # AI 预批阅按它决定松紧，人工批改页也显示它提醒教师保持一致
    grading_preference = Column(JSONB, nullable=True)

    creator = relationship("User", backref="created_assessment_papers")


class AssessmentQuestion(BaseModel):
    __tablename__ = "assessment_questions"

    paper_id = Column(UUID(as_uuid=True), ForeignKey("assessment_papers.id", ondelete="CASCADE"), nullable=False, index=True)
    order_index = Column(Integer, default=0, nullable=False)
    # single, multiple, judge, fill, short, essay, code
    question_type = Column(String(30), nullable=False)
    stem = Column(Text, nullable=False)
    stem_images = Column(JSONB, nullable=True)  # [{object_name, url}]
    options = Column(JSONB, nullable=True)  # 选择题选项
    answer = Column(JSONB, nullable=True)
    analysis = Column(Text, nullable=True)
    # 编程题专用：language=python/javascript/java，
    # test_cases=[{input, expected_output}] 只用于判题，绝不下发学生
    language = Column(String(30), nullable=True)
    test_cases = Column(JSONB, nullable=True)
    starter_code = Column(Text, nullable=True)
    # NULL = 原文没标分值、教师尚未填写；0 是教师明确给出的分值，两者不可混同
    score = Column(Float, nullable=True)
    difficulty = Column(Float, nullable=True)
    tags = Column(JSONB, nullable=True)
    source_chunk = Column(JSONB, nullable=True)  # {start_idx, end_idx, page_range} 溯源

    paper = relationship("AssessmentPaper", backref="questions")


class AssessmentAssignment(BaseModel):
    __tablename__ = "assessment_assignments"
    __table_args__ = (
        UniqueConstraint("paper_id", "user_id", name="uq_assessment_assignments_paper_user"),
    )

    paper_id = Column(UUID(as_uuid=True), ForeignKey("assessment_papers.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    class_id = Column(UUID(as_uuid=True), ForeignKey("classes.id", ondelete="SET NULL"), nullable=True, index=True)
    source_type = Column(String(30), nullable=True)  # class, group, student, whitelist
    status = Column(String(30), default="assigned", nullable=False)
    assigned_at = Column(DateTime(timezone=True), nullable=True)
    due_at = Column(DateTime(timezone=True), nullable=True)

    paper = relationship("AssessmentPaper", backref="assignments")
    user = relationship("User", backref="assessment_assignments")
    class_group = relationship("ClassGroup", backref="assessment_assignments")


class AssessmentAttempt(BaseModel):
    __tablename__ = "assessment_attempts"
    __table_args__ = (
        UniqueConstraint("paper_id", "student_id", name="uq_assessment_attempts_paper_student"),
    )

    paper_id = Column(UUID(as_uuid=True), ForeignKey("assessment_papers.id", ondelete="CASCADE"), nullable=False, index=True)
    student_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    assignment_id = Column(UUID(as_uuid=True), ForeignKey("assessment_assignments.id", ondelete="SET NULL"), nullable=True)
    status = Column(String(30), default="in_progress", nullable=False)  # in_progress, submitted, pending_review
    started_at = Column(DateTime(timezone=True), nullable=True)
    submitted_at = Column(DateTime(timezone=True), nullable=True)
    score = Column(Float, nullable=True)
    suspicious = Column(Boolean, default=False, nullable=False)
    duration_seconds = Column(Integer, nullable=True)

    paper = relationship("AssessmentPaper", backref="attempts")
    student = relationship("User", backref="assessment_attempts")


class AssessmentAnswer(BaseModel):
    __tablename__ = "assessment_answers"
    __table_args__ = (
        UniqueConstraint("attempt_id", "question_id", name="uq_assessment_answers_attempt_question"),
    )

    attempt_id = Column(UUID(as_uuid=True), ForeignKey("assessment_attempts.id", ondelete="CASCADE"), nullable=False, index=True)
    question_id = Column(UUID(as_uuid=True), ForeignKey("assessment_questions.id", ondelete="CASCADE"), nullable=False, index=True)
    answer = Column(JSONB, nullable=True)
    is_correct = Column(Boolean, nullable=True)  # 主观题可为空
    score = Column(Float, default=0.0, nullable=False)
    graded = Column(Boolean, default=False, nullable=False)
    time_spent_ms = Column(Integer, nullable=True)
    # 编程题判题产物：{status, passed, total, cases:[...]}。仅在交卷结算时写入。
    judge_result = Column(JSONB, nullable=True)
    # AI 预批阅产物：分数只是建议值，教师确认前不写进 score；comment 是评分理由
    ai_suggested_score = Column(Float, nullable=True)
    ai_comment = Column(Text, nullable=True)
    ai_graded_at = Column(DateTime(timezone=True), nullable=True)

    attempt = relationship("AssessmentAttempt", backref="answers")
    question = relationship("AssessmentQuestion", backref="answers")


class BehaviorEvent(BaseModel):
    __tablename__ = "behavior_events"

    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    session_id = Column(String(64), nullable=False, index=True)
    attempt_id = Column(UUID(as_uuid=True), ForeignKey("assessment_attempts.id", ondelete="SET NULL"), nullable=True, index=True)
    event_type = Column(String(50), nullable=False)
    payload = Column(JSONB, nullable=True)
    occurred_at = Column(DateTime(timezone=True), nullable=True)

    user = relationship("User", backref="behavior_events")
    attempt = relationship("AssessmentAttempt", backref="behavior_events")