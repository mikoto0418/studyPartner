from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.models.base import BaseModel


class MemoryPage(BaseModel):
    __tablename__ = "memory_pages"

    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    slug = Column(String(160), nullable=False)
    page_type = Column(String(30), default="concept", nullable=False)  # concept, entity, pattern, goal, weakness, event, relationship
    title = Column(String(255), nullable=False)
    summary = Column(Text, nullable=True)
    body = Column(Text, nullable=True)
    category = Column(String(50), default="other", nullable=False)
    tags = Column(JSONB, nullable=True)
    confidence = Column(Float, default=0.5, nullable=False)
    status = Column(String(20), default="active", nullable=False)  # draft, active, superseded, archived, deleted
    source_review_id = Column(UUID(as_uuid=True), ForeignKey("daily_reviews.id", ondelete="SET NULL"), nullable=True)
    version = Column(Integer, default=1, nullable=False)
    last_reviewed_at = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    meta = Column(JSONB, nullable=True)

    __table_args__ = (
        UniqueConstraint("user_id", "slug", name="uq_memory_pages_user_slug"),
    )

    user = relationship("User", backref="memory_pages")
    source_review = relationship("DailyReview", backref="wiki_memory_pages")
    outbound_links = relationship(
        "MemoryLink",
        foreign_keys="MemoryLink.from_page_id",
        back_populates="from_page",
        cascade="all, delete-orphan",
    )
    inbound_links = relationship(
        "MemoryLink",
        foreign_keys="MemoryLink.to_page_id",
        back_populates="to_page",
        cascade="all, delete-orphan",
    )
    sources = relationship(
        "MemorySource",
        back_populates="page",
        cascade="all, delete-orphan",
    )


class MemorySource(BaseModel):
    __tablename__ = "memory_sources"

    page_id = Column(UUID(as_uuid=True), ForeignKey("memory_pages.id", ondelete="CASCADE"), nullable=False, index=True)
    source_type = Column(String(50), nullable=False)  # ai_chat, task_submission, daily_review, bilibili, file, behavior_log
    source_id = Column(String(64), nullable=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    occurred_at = Column(DateTime(timezone=True), nullable=True)
    snippet = Column(Text, nullable=True)
    confidence = Column(Float, default=0.6, nullable=False)
    meta = Column(JSONB, nullable=True)

    page = relationship("MemoryPage", back_populates="sources")
    user = relationship("User", backref="memory_sources")


class MemoryLink(BaseModel):
    __tablename__ = "memory_links"

    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    from_page_id = Column(UUID(as_uuid=True), ForeignKey("memory_pages.id", ondelete="CASCADE"), nullable=False, index=True)
    to_page_id = Column(UUID(as_uuid=True), ForeignKey("memory_pages.id", ondelete="CASCADE"), nullable=False, index=True)
    relation = Column(String(40), default="related_to", nullable=False)  # related_to, prerequisite_of, evidence_for, conflicts_with
    strength = Column(Float, default=0.5, nullable=False)

    __table_args__ = (
        UniqueConstraint("user_id", "from_page_id", "to_page_id", "relation", name="uq_memory_links_user_from_to_relation"),
    )

    user = relationship("User", backref="memory_links")
    from_page = relationship("MemoryPage", foreign_keys=[from_page_id], back_populates="outbound_links")
    to_page = relationship("MemoryPage", foreign_keys=[to_page_id], back_populates="inbound_links")


class MemoryEvent(BaseModel):
    __tablename__ = "memory_events"

    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    page_id = Column(UUID(as_uuid=True), ForeignKey("memory_pages.id", ondelete="SET NULL"), nullable=True, index=True)
    action = Column(String(40), nullable=False)  # create, update, merge, split, archive, delete, confirm, reject, lint, ingest
    before = Column(JSONB, nullable=True)
    after = Column(JSONB, nullable=True)
    reason = Column(Text, nullable=True)
    operator = Column(String(30), default="system", nullable=False)  # system, student, teacher, admin
    review_id = Column(UUID(as_uuid=True), ForeignKey("daily_reviews.id", ondelete="SET NULL"), nullable=True)
    meta = Column(JSONB, nullable=True)

    user = relationship("User", backref="memory_events")
    page = relationship("MemoryPage", backref="events")
    review = relationship("DailyReview", backref="memory_events")


class MemoryReviewTask(BaseModel):
    __tablename__ = "memory_review_tasks"

    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    page_id = Column(UUID(as_uuid=True), ForeignKey("memory_pages.id", ondelete="SET NULL"), nullable=True, index=True)
    task_type = Column(String(40), nullable=False)  # create, update, merge, delete, confirm
    payload = Column(JSONB, nullable=True)
    status = Column(String(20), default="pending", nullable=False)  # pending, approved, rejected, expired
    created_by = Column(String(30), default="system", nullable=False)
    handled_at = Column(DateTime(timezone=True), nullable=True)
    handled_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    handled_reason = Column(Text, nullable=True)

    user = relationship("User", foreign_keys=[user_id], backref="memory_review_tasks")
    page = relationship("MemoryPage", backref="review_tasks")
    handler = relationship("User", foreign_keys=[handled_by])