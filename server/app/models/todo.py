from sqlalchemy import Column, String, Text, DateTime, Integer, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.models.base import BaseModel

class Todo(BaseModel):
    __tablename__ = "todos"

    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    priority = Column(String(50), default="medium", nullable=False)  # low, medium, high, urgent
    status = Column(String(50), default="pending", nullable=False)   # pending, completed, cancelled
    category = Column(String(100), nullable=True)
    due_date = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    sort_order = Column(Integer, default=0, nullable=False)

    # Relationships
    user = relationship("User", backref="todos")
