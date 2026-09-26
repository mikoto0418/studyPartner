import os
from typing import List, Optional
from pydantic import AnyHttpUrl, BeforeValidator, Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing_extensions import Annotated

def assemble_cors_origins(v: str | List[str]) -> List[str]:
    if isinstance(v, str) and not v.startswith("["):
        return [i.strip() for i in v.split(",")]
    elif isinstance(v, (list, str)):
        return v
    raise ValueError(v)

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_ignore_empty=True,
        extra="ignore"
    )

    APP_NAME: str = "AI伴学与智能体协同平台"
    APP_ENV: str = "development"
    APP_DEBUG: bool = True
    ENABLE_INLINE_SCHEDULER: bool = False

    # ========== CORS ==========
    CORS_ORIGINS: Annotated[
        List[str], BeforeValidator(assemble_cors_origins)
    ] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    # ========== PostgreSQL ==========
    POSTGRES_HOST: str = "127.0.0.1"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_DB: str = "studypartner"
    DATABASE_URI: Optional[str] = None

    @property
    def async_database_uri(self) -> str:
        if self.DATABASE_URI:
            return self.DATABASE_URI
        return f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    # ========== Redis ==========
    REDIS_HOST: str = "127.0.0.1"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: Optional[str] = None
    REDIS_DB: int = 0

    @property
    def redis_url(self) -> str:
        if self.REDIS_PASSWORD:
            return f"redis://:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

    # ========== JWT ==========
    JWT_SECRET_KEY: str = "SUPER_SECRET_KEY_PLEASE_CHANGE_IN_PRODUCTION"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # Default to 24 hours for easy dev
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # ========== MinIO ==========
    MINIO_ENDPOINT: str = "127.0.0.1:9000"
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin"
    MINIO_SECURE: bool = False
    MINIO_BUCKET_NAME: str = "studypartner-files"

    # ========== Qdrant ==========
    QDRANT_HOST: str = "127.0.0.1"
    QDRANT_PORT: int = 6333
    QDRANT_COLLECTION: str = "knowledge_base"

    # ========== 判题沙箱（go-judge） ==========
    # 编程题在这里编译运行学生代码。未配置时判题接口会明确报错而不是静默判错。
    JUDGE_BASE_URL: str = "http://127.0.0.1:5050"
    JUDGE_AUTH_TOKEN: str = ""
    # 单次运行上限：2 秒 CPU、256MB 内存、64 个子进程
    JUDGE_CPU_LIMIT_NS: int = 2_000_000_000
    JUDGE_MEMORY_LIMIT_BYTES: int = 256 * 1024 * 1024
    JUDGE_PROC_LIMIT: int = 64
    # 编译类语言（java/c++）需要的额外时间
    JUDGE_COMPILE_CPU_LIMIT_NS: int = 12_000_000_000
    JUDGE_COMPILE_MEMORY_LIMIT_BYTES: int = 512 * 1024 * 1024
    JUDGE_OUTPUT_LIMIT_BYTES: int = 64 * 1024
    JUDGE_TIMEOUT_SECONDS: float = 30.0
    # 单个作答的编程题自测次数上限。自测只跑样例，但仍要防住刷接口占满沙箱。
    JUDGE_DRY_RUN_LIMIT: int = 60

    # ========== SiliconFlow (LLM) ==========
    SILICONFLOW_API_KEY: str = ""
    SILICONFLOW_BASE_URL: str = "https://api.siliconflow.cn/v1"
    SILICONFLOW_CHAT_API_KEY: str = ""
    SILICONFLOW_CHAT_BASE_URL: Optional[str] = None
    SILICONFLOW_CHAT_MODEL: str = "Qwen/Qwen2.5-7B-Instruct"
    SILICONFLOW_EMBEDDING_API_KEY: str = ""
    SILICONFLOW_EMBEDDING_BASE_URL: Optional[str] = None
    SILICONFLOW_EMBEDDING_MODEL: str = "BAAI/bge-large-zh-v1.5"
    LLM_CHAT_TIMEOUT_SECONDS: float = 60.0
    LEARNING_PATH_LLM_TIMEOUT_SECONDS: float = 90.0

    # ========== 拆题专用 LLM 配置 (OpenAI 兼容接口) ==========
    QUESTION_PARSING_API_KEY: str = ""
    QUESTION_PARSING_BASE_URL: str = ""
    QUESTION_PARSING_MODEL: str = ""

    # ========== SMTP (Email) ==========
    SMTP_HOST: str = "smtp.qq.com"
    SMTP_PORT: int = 465
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""  # auth code
    SMTP_FROM_EMAIL: str = ""

settings = Settings()
