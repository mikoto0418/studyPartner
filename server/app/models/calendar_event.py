from sqlalchemy import Column, String, Text, DateTime, Boolean, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.models.base import BaseModel

class CalendarEvent(BaseModel):
    __tablename__ = "calendar_events"

    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    event_type = Column(String(50), default="personal", nullable=False)  # personal, task, countdown, teacher_assigned
    status = Column(String(50), default="planned", nullable=False)       # planned, in_progress, completed, cancelled
    start_time = Column(DateTime(timezone=True), nullable=False)
    end_time = Column(DateTime(timezone=True), nullable=False)
    all_day = Column(Boolean, default=False, nullable=False)
    color = Column(String(50), nullable=True)
    related_task_id = Column(UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="SET NULL"), nullable=True)
    related_countdown_id = Column(UUID(as_uuid=True), nullable=True)

    # Relationships
    user = relationship("User", foreign_keys=[user_id], backref="calendar_events")
    creator = relationship("User", foreign_keys=[created_by], backref="created_calendar_events")
    task = relationship("Task", backref="calendar_events")
