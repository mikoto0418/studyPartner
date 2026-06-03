from sqlalchemy import Column, String, Integer, Boolean, Float, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.models.base import BaseModel

class LLMProviderConfig(BaseModel):
    __tablename__ = "llm_provider_configs"

    provider_name = Column(String(64), nullable=False) # e.g. siliconflow, openai
    display_name = Column(String(128), nullable=True)
    base_url = Column(String(512), nullable=False)
    api_key_enc = Column(String(512), nullable=False) # Store API key (plaintext/simple hash in MVP)
    model_name = Column(String(128), nullable=False)
    task_type = Column(String(32), nullable=False) # e.g. student_chat, daily_review, memory_extract, RAG
    priority = Column(Integer, default=0, nullable=False)
    enabled = Column(Boolean, default=True, nullable=False)
    daily_quota = Column(Integer, nullable=True)
    used_today = Column(Integer, default=0, nullable=False)
    rpm_limit = Column(Integer, nullable=True)
    tpm_limit = Column(Integer, nullable=True)
    fallback_provider_id = Column(UUID(as_uuid=True), ForeignKey("llm_provider_configs.id", ondelete="SET NULL"), nullable=True)
    extra_params = Column(JSONB, nullable=True)

    # Relationships
    fallback_provider = relationship("LLMProviderConfig", remote_side="LLMProviderConfig.id", backref="primary_providers")

class LLMUsageLog(BaseModel):
    __tablename__ = "llm_usage_logs"

    user_id = Column(UUID(as_uuid=True), nullable=True, index=True) # Triggering user (can be null for cron tasks)
    provider_config_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    task_type = Column(String(32), nullable=False)
    model_name = Column(String(128), nullable=False)
    input_tokens = Column(Integer, nullable=True)
    output_tokens = Column(Integer, nullable=True)
    total_tokens = Column(Integer, nullable=True)
    cost = Column(Float, nullable=True) # Estimated cost
    latency_ms = Column(Integer, nullable=True)
    success = Column(Boolean, default=True, nullable=False)
    error_message = Column(String, nullable=True)
    request_id = Column(String(128), nullable=True)
    context_metadata = Column(JSONB, nullable=True)
