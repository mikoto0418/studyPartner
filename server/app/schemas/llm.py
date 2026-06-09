from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class LLMProviderConfigOut(BaseModel):
    id: UUID
    provider_name: str
    display_name: Optional[str] = None
    base_url: str
    model_name: str
    task_type: str
    priority: int
    enabled: bool
    rpm_limit: Optional[int] = None
    tpm_limit: Optional[int] = None
    has_api_key: bool = False
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class LLMConfigUpsertReq(BaseModel):
    provider_name: str = "siliconflow"
    display_name: Optional[str] = "SiliconFlow"
    base_url: str = "https://api.siliconflow.cn/v1"
    api_key: Optional[str] = Field(default=None, min_length=8)
    chat_model: str
    embedding_model: str
    task_types: List[str] = Field(default_factory=lambda: [
        "student_chat",
        "daily_review",
        "memory_extract",
        "memory_update",
        "knowledge_qa",
        "document_summary",
    ])
    enabled: bool = True
    rpm_limit: Optional[int] = None
    tpm_limit: Optional[int] = None


class LLMConnectionTestReq(BaseModel):
    provider_name: str = "siliconflow"
    base_url: str = "https://api.siliconflow.cn/v1"
    api_key: str = Field(..., min_length=8)
    model_name: str


class LLMConnectionTestOut(BaseModel):
    provider_name: str
    model_name: str
    latency_ms: int
    ok: bool


class LLMUsageLogOut(BaseModel):
    id: UUID
    task_type: str
    model_name: str
    total_tokens: int = 0
    latency_ms: Optional[int] = None
    success: bool
    error_message: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class AdminOverviewOut(BaseModel):
    total_users: int
    llm_calls_today: int
    storage_bytes: int
    service_status: str
    recent_usage_logs: List[LLMUsageLogOut]


class AdminRuntimeSettingsOut(BaseModel):
    app_env: str
    app_debug: bool
    inline_scheduler_enabled: bool
    smtp_configured: bool
    smtp_host: str
    smtp_from_email: Optional[str] = None
    minio_endpoint: str
    minio_bucket_name: str
    qdrant_endpoint: str
    llm_provider_count: int
    enabled_llm_provider_count: int
