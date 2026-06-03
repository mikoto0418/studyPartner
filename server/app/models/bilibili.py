from sqlalchemy import Column, String, Text, Integer, Boolean, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from app.models.base import BaseModel

class StudyTimeLog(BaseModel):
    __tablename__ = "study_time_logs"

    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    session_id = Column(String(64), nullable=False, index=True)
    status = Column(String(20), default="active", nullable=False) # active, completed, timeout
    start_time = Column(DateTime(timezone=True), nullable=False)
    end_time = Column(DateTime(timezone=True), nullable=True)
    duration_seconds = Column(Integer, nullable=True)
    source = Column(String(32), default="platform", nullable=False) # platform, bilibili

    # Relationships
    user = relationship("User", backref="study_time_logs")

class BilibiliResource(BaseModel):
    __tablename__ = "bilibili_resources"

    creator_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    bvid = Column(String(32), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    cover_url = Column(String(512), nullable=True)
    author_name = Column(String(128), nullable=True)
    total_episodes = Column(Integer, default=1, nullable=False)
    total_duration = Column(Integer, nullable=True) # in seconds
    category = Column(String(64), nullable=True, index=True)
    episodes_info = Column(JSONB, nullable=True)
    is_shared = Column(Boolean, default=False, nullable=False)

    __table_args__ = (
        UniqueConstraint("bvid", "creator_id", name="uq_bilibili_resources_bvid_creator"),
    )

    # Relationships
    creator = relationship("User", backref="bilibili_resources")

class BilibiliWatchLog(BaseModel):
    __tablename__ = "bilibili_watch_logs"

    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    resource_id = Column(UUID(as_uuid=True), ForeignKey("bilibili_resources.id", ondelete="CASCADE"), nullable=False, index=True)
    event_type = Column(String(20), nullable=False) # open, heartbeat, close, manual_complete
    episode_number = Column(Integer, default=1, nullable=False)
    watch_duration = Column(Integer, default=0, nullable=False) # seconds since last update
    is_completed = Column(Boolean, default=False, nullable=False)

    # Relationships
    user = relationship("User", backref="bilibili_watch_logs")
    resource = relationship("BilibiliResource", backref="watch_logs")
