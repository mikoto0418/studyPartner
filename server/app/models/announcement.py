from sqlalchemy import Column, String, Text, Boolean, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.models.base import BaseModel
import uuid

class Announcement(BaseModel):
    __tablename__ = "announcements"

    creator_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    content = Column(Text, nullable=False)
    status = Column(String(50), default="published", nullable=False)  # draft, published, expired, withdrawn
    target_type = Column(String(50), default="all", nullable=False)  # all, all_students, all_teachers, specific_users
    is_pinned = Column(Boolean, default=False, nullable=False)
    publish_at = Column(DateTime(timezone=True), nullable=True)
    expire_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    creator = relationship("User", backref="created_announcements")

class AnnouncementReceiver(BaseModel):
    __tablename__ = "announcement_receivers"

    # We can omit timestamps from base and subclass directly from DeclarativeBase, but subclassing BaseModel is easier.
    announcement_id = Column(UUID(as_uuid=True), ForeignKey("announcements.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

class AnnouncementRead(BaseModel):
    __tablename__ = "announcement_reads"

    announcement_id = Column(UUID(as_uuid=True), ForeignKey("announcements.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    read_at = Column(DateTime(timezone=True), nullable=True)
