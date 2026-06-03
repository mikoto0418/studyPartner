from sqlalchemy import Column, String, Text, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.models.base import BaseModel

class Notification(BaseModel):
    __tablename__ = "notifications"

    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    content = Column(Text, nullable=False)
    notification_type = Column(String(50), default="system", nullable=False)  # announcement, task_assigned, etc.
    read_at = Column(DateTime(timezone=True), nullable=True)
    link_url = Column(String(255), nullable=True)

    # Relationships
    user = relationship("User", backref="notifications")
