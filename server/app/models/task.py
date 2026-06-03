from sqlalchemy import Column, String, Text, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.models.base import BaseModel

class Task(BaseModel):
    __tablename__ = "tasks"

    creator_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    priority = Column(String(50), default="medium", nullable=False)  # low, medium, high, urgent
    status = Column(String(50), default="in_progress", nullable=False)  # not_started, in_progress, completed, cancelled
    start_date = Column(DateTime(timezone=True), nullable=True)
    due_date = Column(DateTime(timezone=True), nullable=True)
    attachment_ids = Column(JSONB, nullable=True)  # List of UUIDs mapping to files

    # Relationships
    creator = relationship("User", backref="created_tasks")

class TaskAssignee(BaseModel):
    __tablename__ = "task_assignees"

    task_id = Column(UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    status = Column(String(50), default="not_started", nullable=False)  # not_started, in_progress, submitted, completed, rejected, overdue
    assigned_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    task = relationship("Task", backref="assignees")
    user = relationship("User", backref="assigned_tasks")

class TaskSubmission(BaseModel):
    __tablename__ = "task_submissions"

    task_id = Column(UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True)
    assignee_id = Column(UUID(as_uuid=True), ForeignKey("task_assignees.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)  # The submitter
    content = Column(Text, nullable=True)
    attachment_ids = Column(JSONB, nullable=True)  # File UUIDs
    feedback = Column(Text, nullable=True)
    reviewed_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    task = relationship("Task", backref="submissions")
    user = relationship("User", foreign_keys=[user_id], backref="submissions")
    reviewer = relationship("User", foreign_keys=[reviewed_by], backref="reviewed_submissions")
