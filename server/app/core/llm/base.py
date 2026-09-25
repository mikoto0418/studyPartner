from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import AsyncIterator, Optional, List, Dict, Any, Union

class LLMProviderError(RuntimeError):
    """Provider-side error that should be shown to admins/operators."""

    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        retry_after: Optional[float] = None,
    ):
        super().__init__(message)
        # 供路由层判断是否值得重试；非 HTTP 错误（如响应缺字段）保持 None。
        self.status_code = status_code
        # 网关 429/503 常带 Retry-After，指明还要等多少秒，优先于本地退避估算。
        self.retry_after = retry_after

@dataclass
class ChatMessage:
    role: str          # "system" | "user" | "assistant"
    content: str

@dataclass
class ChatResponse:
    content: str
    model: str
    provider: str
    usage: Dict[str, int]        # {"prompt_tokens": int, "completion_tokens": int, "total_tokens": int}
    finish_reason: str
    latency_ms: float

@dataclass
class EmbeddingResponse:
    embedding: List[float]
    model: str
    provider: str
    usage: Dict[str, int]

class LLMProvider(ABC):
    """LLM Provider Abstract Base Class"""

    def __init__(self, provider_name: str, config: Dict[str, Any]):
        self.provider_name = provider_name
        self.config = config

    @abstractmethod
    async def chat_completion(
        self,
        messages: List[ChatMessage],
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        stream: bool = False,
        **kwargs
    ) -> Union[ChatResponse, AsyncIterator[str]]:
        """Send chat completion request, supporting stream or block options"""
        pass

    @abstractmethod
    async def embedding(
        self,
        text: Union[str, List[str]],
        model: str
    ) -> Union[EmbeddingResponse, List[EmbeddingResponse]]:
        """Generate text embedding vector"""
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if provider service is healthy and responsive"""
        pass

    @abstractmethod
    async def get_available_models(self) -> List[str]:
        """Fetch list of available models from provider"""
        pass
