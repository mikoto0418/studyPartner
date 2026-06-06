from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.models.base import BaseModel


class ClassGroup(BaseModel):
    __tablename__ = "classes"

    teacher_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(120), nullable=False)
    description = Column(Text, nullable=True)
    grade = Column(String(50), nullable=True)
    subject = Column(String(120), nullable=True)
    status = Column(String(30), default="active", nullable=False)

    teacher = relationship("User", backref="teaching_classes")


class ClassMember(BaseModel):
    __tablename__ = "class_members"

    class_id = Column(UUID(as_uuid=True), ForeignKey("classes.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String(30), default="student", nullable=False)
    joined_at = Column(DateTime(timezone=True), nullable=True)
    status = Column(String(30), default="active", nullable=False)

    class_group = relationship("ClassGroup", backref="members")
    user = relationship("User", backref="class_memberships")


class LearningPathTask(BaseModel):
    __tablename__ = "learning_path_tasks"

    creator_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    class_id = Column(UUID(as_uuid=True), ForeignKey("classes.id", ondelete="SET NULL"), nullable=True, index=True)
    title = Column(String(255), nullable=False)
    goal = Column(Text, nullable=False)
    planning_text = Column(Text, nullable=True)
    description = Column(Text, nullable=True)
    status = Column(String(30), default="draft", nullable=False)
    due_date = Column(DateTime(timezone=True), nullable=True)
    published_at = Column(DateTime(timezone=True), nullable=True)
    ai_plan = Column(JSONB, nullable=True)

    creator = relationship("User", backref="created_learning_paths")
    class_group = relationship("ClassGroup", backref="learning_paths")


class LearningPathStage(BaseModel):
    __tablename__ = "learning_path_stages"

    task_id = Column(UUID(as_uuid=True), ForeignKey("learning_path_tasks.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(180), nullable=False)
    description = Column(Text, nullable=True)
    order_index = Column(Integer, default=0, nullable=False)

    task = relationship("LearningPathTask", backref="stages")


class LearningPathNode(BaseModel):
    __tablename__ = "learning_path_nodes"

    task_id = Column(UUID(as_uuid=True), ForeignKey("learning_path_tasks.id", ondelete="CASCADE"), nullable=False, index=True)
    stage_id = Column(UUID(as_uuid=True), ForeignKey("learning_path_stages.id", ondelete="CASCADE"), nullable=True, index=True)
    key = Column(String(80), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    node_type = Column(String(50), default="learning", nullable=False)
    order_index = Column(Integer, default=0, nullable=False)
    estimated_minutes = Column(Integer, default=45, nullable=False)
    required = Column(Boolean, default=True, nullable=False)
    config = Column(JSONB, nullable=True)

    task = relationship("LearningPathTask", backref="nodes")
    stage = relationship("LearningPathStage", backref="nodes")


class LearningPathEdge(BaseModel):
    __tablename__ = "learning_path_edges"

    task_id = Column(UUID(as_uuid=True), ForeignKey("learning_path_tasks.id", ondelete="CASCADE"), nullable=False, index=True)
    source_node_id = Column(UUID(as_uuid=True), ForeignKey("learning_path_nodes.id", ondelete="CASCADE"), nullable=True)
    target_node_id = Column(UUID(as_uuid=True), ForeignKey("learning_path_nodes.id", ondelete="CASCADE"), nullable=True)
    source_key = Column(String(80), nullable=False)
    target_key = Column(String(80), nullable=False)

    task = relationship("LearningPathTask", backref="edges")
    source_node = relationship("LearningPathNode", foreign_keys=[source_node_id], backref="outgoing_edges")
    target_node = relationship("LearningPathNode", foreign_keys=[target_node_id], backref="incoming_edges")


class LearningPathResource(BaseModel):
    __tablename__ = "learning_path_resources"

    task_id = Column(UUID(as_uuid=True), ForeignKey("learning_path_tasks.id", ondelete="CASCADE"), nullable=False, index=True)
    node_id = Column(UUID(as_uuid=True), ForeignKey("learning_path_nodes.id", ondelete="CASCADE"), nullable=True, index=True)
    resource_type = Column(String(50), nullable=False)
    title = Column(String(255), nullable=True)
    url = Column(String(500), nullable=True)
    bv_id = Column(String(32), nullable=True)
    file_id = Column(UUID(as_uuid=True), ForeignKey("files.id", ondelete="SET NULL"), nullable=True)
    metadata_json = Column(JSONB, nullable=True)

    task = relationship("LearningPathTask", backref="resources")
    node = relationship("LearningPathNode", backref="resources")


class LearningPathAssignee(BaseModel):
    __tablename__ = "learning_path_assignees"

    task_id = Column(UUID(as_uuid=True), ForeignKey("learning_path_tasks.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    class_id = Column(UUID(as_uuid=True), ForeignKey("classes.id", ondelete="SET NULL"), nullable=True, index=True)
    status = Column(String(50), default="not_started", nullable=False)
    progress_percent = Column(Float, default=0.0, nullable=False)
    assigned_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    task = relationship("LearningPathTask", backref="assignees")
    user = relationship("User", backref="assigned_learning_paths")
    class_group = relationship("ClassGroup", backref="learning_path_assignees")


class LearningNodeProgress(BaseModel):
    __tablename__ = "learning_node_progress"

    task_id = Column(UUID(as_uuid=True), ForeignKey("learning_path_tasks.id", ondelete="CASCADE"), nullable=False, index=True)
    node_id = Column(UUID(as_uuid=True), ForeignKey("learning_path_nodes.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    status = Column(String(50), default="locked", nullable=False)
    score = Column(Float, nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    submitted_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    task = relationship("LearningPathTask", backref="node_progress")
    node = relationship("LearningPathNode", backref="progress_records")
    user = relationship("User", backref="learning_node_progress")


class LearningNodeSubmission(BaseModel):
    __tablename__ = "learning_node_submissions"

    task_id = Column(UUID(as_uuid=True), ForeignKey("learning_path_tasks.id", ondelete="CASCADE"), nullable=False, index=True)
    node_id = Column(UUID(as_uuid=True), ForeignKey("learning_path_nodes.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    content = Column(Text, nullable=True)
    attachment_ids = Column(JSONB, nullable=True)
    review_status = Column(String(50), default="pending", nullable=False)
    score = Column(Float, nullable=True)
    feedback = Column(Text, nullable=True)
    follow_up = Column(Text, nullable=True)
    reviewed_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    reopen_until = Column(DateTime(timezone=True), nullable=True)

    task = relationship("LearningPathTask", backref="node_submissions")
    node = relationship("LearningPathNode", backref="submissions")
    user = relationship("User", foreign_keys=[user_id], backref="learning_submissions")
    reviewer = relationship("User", foreign_keys=[reviewed_by], backref="reviewed_learning_submissions")


class ClassMemorySnapshot(BaseModel):
    __tablename__ = "class_memory_snapshots"

    class_id = Column(UUID(as_uuid=True), ForeignKey("classes.id", ondelete="CASCADE"), nullable=False, index=True)
    snapshot_date = Column(DateTime(timezone=True), nullable=False)
    summary = Column(Text, nullable=True)
    metrics = Column(JSONB, nullable=True)
    trend = Column(JSONB, nullable=True)
    generated_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    class_group = relationship("ClassGroup", backref="memory_snapshots")


class StudentGrowthReport(BaseModel):
    __tablename__ = "student_growth_reports"

    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    report_period = Column(String(50), default="weekly", nullable=False)
    summary = Column(Text, nullable=True)
    metrics = Column(JSONB, nullable=True)
    parent_view_enabled = Column(Boolean, default=False, nullable=False)

    user = relationship("User", backref="growth_reports")
