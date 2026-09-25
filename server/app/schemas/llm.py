from datetime import datetime
from typing import Any, List, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


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


CHAT_TASK_TYPES: List[str] = [
    "student_chat",
    "daily_review",
    "memory_extract",
    "memory_update",
    "knowledge_qa",
    "learning_path_generate",
    "document_summary",
    "question_parsing",
]
EMBEDDING_TASK_TYPES: List[str] = ["knowledge_embedding"]


class LLMConfigUpsertReq(BaseModel):
    provider_name: str = "siliconflow"
    display_name: Optional[str] = "SiliconFlow"
    base_url: Optional[str] = None
    api_key: Optional[str] = Field(default=None, min_length=8)
    chat_base_url: Optional[str] = None
    chat_api_key: Optional[str] = Field(default=None, min_length=8)
    chat_model: str
    embedding_base_url: Optional[str] = None
    embedding_api_key: Optional[str] = Field(default=None, min_length=8)
    embedding_model: str
    task_types: List[str] = Field(default_factory=lambda: list(CHAT_TASK_TYPES))
    enabled: bool = True
    rpm_limit: Optional[int] = None
    tpm_limit: Optional[int] = None


class LLMConnectionTestReq(BaseModel):
    provider_name: str = "siliconflow"
    base_url: Optional[str] = None
    # 留空表示「按保存态测试」：后端取该通道已存的密钥、Base URL 和模型名。
    api_key: Optional[str] = Field(default=None, min_length=8)
    model_name: Optional[str] = None
    endpoint_type: Literal["chat", "embedding"] = "chat"
    # 指定要读哪条通道的已存配置；不填则按 endpoint_type 在对话/嵌入通道里挑优先级最高的。
    task_type: Optional[str] = None

    @field_validator("api_key", "base_url", "model_name", "task_type", mode="before")
    @classmethod
    def _blank_to_none(cls, value: Any) -> Any:
        if isinstance(value, str) and not value.strip():
            return None
        return value


class LLMConnectionTestOut(BaseModel):
    provider_name: str
    model_name: str
    latency_ms: int
    ok: bool
    # form=本次用的是表单里临时填的密钥；saved=用的是已保存通道的密钥
    key_source: Literal["form", "saved"] = "form"


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
