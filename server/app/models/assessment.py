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
    total_score = Column(Float, default=0.0, nullable=False)
    publish_target = Column(JSONB, nullable=True)  # {type: class/group/student, ids, whitelist, blacklist}
    publish_at = Column(DateTime(timezone=True), nullable=True)  # 预约发布时间
    published_at = Column(DateTime(timezone=True), nullable=True)  # 实际发布时间

    creator = relationship("User", backref="created_assessment_papers")


class AssessmentQuestion(BaseModel):
    __tablename__ = "assessment_questions"

    paper_id = Column(UUID(as_uuid=True), ForeignKey("assessment_papers.id", ondelete="CASCADE"), nullable=False, index=True)
    order_index = Column(Integer, default=0, nullable=False)
    # single, multiple, judge, fill, short, essay
    question_type = Column(String(30), nullable=False)
    stem = Column(Text, nullable=False)
    stem_images = Column(JSONB, nullable=True)  # [{object_name, url}]
    options = Column(JSONB, nullable=True)  # 选择题选项
    answer = Column(JSONB, nullable=True)
    analysis = Column(Text, nullable=True)
    score = Column(Float, default=0.0, nullable=False)
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
    status = Column(String(30), default="in_progress", nullable=False)  # in_progress, submitted, expired
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