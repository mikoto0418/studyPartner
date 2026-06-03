from sqlalchemy import Column, String, Text, Boolean, Integer, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.models.base import BaseModel

class Note(BaseModel):
    __tablename__ = "notes"

    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(255), nullable=True)
    content = Column(Text, nullable=False)
    color = Column(String(100), nullable=True)  # e.g., low-sat colors: bg-amber-50, etc.
    category = Column(String(100), nullable=True)
    is_pinned = Column(Boolean, default=False, nullable=False)
    sort_order = Column(Integer, default=0, nullable=False)

    # Relationships
    user = relationship("User", backref="notes")
