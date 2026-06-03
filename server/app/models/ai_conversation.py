from sqlalchemy import Column, String, Text, Integer, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.models.base import BaseModel

class AIConversation(BaseModel):
    __tablename__ = "ai_conversations"

    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(255), nullable=True)
    conversation_type = Column(String(32), default="student_chat", nullable=False) # student_chat, knowledge_qa, task_breakdown, plan_generate
    model_name = Column(String(128), nullable=True)
    context_config = Column(JSONB, nullable=True)
    message_count = Column(Integer, default=0, nullable=False)
    last_message_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    user = relationship("User", backref="conversations")

class AIMessage(BaseModel):
    __tablename__ = "ai_messages"

    conversation_id = Column(UUID(as_uuid=True), ForeignKey("ai_conversations.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String(16), nullable=False) # system, user, assistant
    content = Column(Text, nullable=False)
    token_count = Column(Integer, nullable=True)
    model_name = Column(String(128), nullable=True)
    context_metadata = Column(JSONB, nullable=True)

    # Relationships
    conversation = relationship("AIConversation", backref="messages")
