from sqlalchemy import Column, String, Text, Float, Integer, Date, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.models.base import BaseModel

class DailyReview(BaseModel):
    __tablename__ = "daily_reviews"

    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    review_date = Column(Date, nullable=False)
    summary = Column(Text, nullable=True)
    study_stats = Column(JSONB, nullable=True)
    task_stats = Column(JSONB, nullable=True)
    behavior_stats = Column(JSONB, nullable=True)
    ai_suggestion = Column(Text, nullable=True)
    new_memories = Column(JSONB, nullable=True) # JSON list of new memory snippets
    updated_memories = Column(JSONB, nullable=True) # JSON list of updated memory snippets
    model_name = Column(String(128), nullable=True)
    token_count = Column(Integer, nullable=True)
    status = Column(String(20), default="pending", nullable=False) # pending, processing, completed, failed
    error_message = Column(Text, nullable=True)

    # Relationships
    user = relationship("User", backref="daily_reviews")

class StudentMemory(BaseModel):
    __tablename__ = "student_memories"

    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    memory_type = Column(String(20), nullable=False) # short_term, long_term
    category = Column(String(32), default="other", nullable=False) # learning_preference, study_habit, interest_area, weakness, goal, etc.
    content = Column(Text, nullable=False)
    evidence = Column(Text, nullable=True)
    confidence = Column(Float, default=0.5, nullable=False)
    status = Column(String(20), default="active", nullable=False) # active, superseded, archived, deleted
    source_review_id = Column(UUID(as_uuid=True), ForeignKey("daily_reviews.id", ondelete="SET NULL"), nullable=True)
    context_metadata = Column(JSONB, nullable=True)
    version = Column(Integer, default=1, nullable=False)
    superseded_by = Column(UUID(as_uuid=True), ForeignKey("student_memories.id", ondelete="SET NULL"), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    user = relationship("User", backref="memories")
    source_review = relationship("DailyReview", backref="generated_memories")
    superseded_memory = relationship("StudentMemory", remote_side="StudentMemory.id", backref="newer_memories")
