import asyncio
import time
import logging
from typing import Optional, List, Dict, Any, Union, AsyncIterator
from uuid import UUID

import httpx

from app.core.database import SessionLocal
from app.models.llm import LLMUsageLog, LLMProviderConfig
from app.core.llm.base import LLMProvider, ChatMessage, ChatResponse, LLMProviderError
from app.core.security import decrypt_secret

logger = logging.getLogger(__name__)
OPENAI_COMPATIBLE_PROVIDERS = {
    "siliconflow", "xiaomi", "xiaomi_token_plan", "openai_compatible",
    "modelscope", "dashscope",
}

PROVIDER_DEFAULT_BASE_URLS = {
    "modelscope": "https://api-inference.modelscope.cn/v1",
    "dashscope": "https://dashscope.aliyuncs.com/compatible-mode/v1",
}

# 聚合网关（new-api 之类）转发到上游时会偶发 5xx 和「假 401」——同一把密钥
# 连续调用会随机失败又成功。拆题这类长任务只有一条通道，撞上一次抖动整份试卷
# 就废了，所以在同一通道内对瞬时错误重试；400/404 这类配置错误重试没有意义。
RETRYABLE_STATUS_CODES = {401, 403, 408, 409, 429, 500, 502, 503, 504}
PROVIDER_ATTEMPTS = 3
RETRY_BACKOFF_SECONDS = 1.0
# 限流（429）与瞬时抖动不同：网关的配额窗口是按分钟计的，等一两秒不会恢复。
# 给它更长的退避和更多次尝试；若响应带 Retry-After，就以网关给的秒数为准。
RATE_LIMIT_ATTEMPTS = 6
RATE_LIMIT_BACKOFF_SECONDS = 15.0
MAX_RETRY_AFTER_SECONDS = 60.0


def _retry_delay(exc: Exception, attempt: int) -> float:
    retry_after = getattr(exc, "retry_after", None)
    if retry_after:
        return min(float(retry_after), MAX_RETRY_AFTER_SECONDS)
    if getattr(exc, "status_code", None) == 429:
        return RATE_LIMIT_BACKOFF_SECONDS * attempt
    return RETRY_BACKOFF_SECONDS * attempt


def _attempts_for(exc: Exception, default: int) -> int:
    return RATE_LIMIT_ATTEMPTS if getattr(exc, "status_code", None) == 429 else default


def _is_retryable(exc: Exception) -> bool:
    if isinstance(exc, (TimeoutError, asyncio.TimeoutError)):
        return True
    if isinstance(exc, httpx.TransportError):
        return True
    if isinstance(exc, LLMProviderError):
        # status_code 为 None 表示不是 HTTP 层错误（如响应缺字段），不值得重试。
        return exc.status_code in RETRYABLE_STATUS_CODES
    return False

class RateLimiter:
    """Simple rate limiter checking user daily quotas and model configuration rules"""

    async def check_limit(self, provider_name: str, user_id: Optional[UUID]) -> bool:
        # MVP: No strict limits checked, always return True
        return True

    async def record_usage(self, provider_name: str, user_id: Optional[UUID], tokens: int) -> None:
        # MVP: Record tokens usage locally (currently log only)
        pass

class UsageLogger:
    """Logs LLM usage data and latency stats directly to the database"""

    async def log_call(
        self,
        provider: str,
        model: str,
        task_type: str,
        user_id: Optional[UUID],
        tokens_in: int,
        tokens_out: int,
        latency_ms: float,
        status: str
    ) -> None:
        try:
            async with SessionLocal() as db:
                log_entry = LLMUsageLog(
                    user_id=user_id,
                    task_type=task_type,
                    model_name=model,
                    input_tokens=tokens_in,
                    output_tokens=tokens_out,
                    total_tokens=tokens_in + tokens_out,
                    latency_ms=int(latency_ms),
                    success=(status == "success"),
                    error_message=None if status == "success" else status
                )
                db.add(log_entry)
                await db.commit()
        except Exception as e:
            logger.error(f"Failed to log LLM usage: {e}", exc_info=True)

class LLMRouter:
    """
    Task type driven LLM Router.
    Routes queries dynamically based on DB configurations or explicit environment configuration.
    """

    def __init__(self, providers: Dict[str, LLMProvider]):
        self.providers = providers
        self.rate_limiter = RateLimiter()
        self.usage_logger = UsageLogger()

    async def _close_provider_client(self, provider: LLMProvider) -> None:
        http_client = getattr(provider, "http_client", None)
        if not http_client:
            return
        try:
            await http_client.aclose()
        except Exception as exc:
            logger.warning(f"Failed to close LLM provider client: {exc}")

    async def _chat_with_retry(
        self,
        provider: LLMProvider,
        provider_name: str,
        model: str,
        attempts: int = PROVIDER_ATTEMPTS,
        **call_kwargs,
    ):
        """在同一通道内对瞬时错误重试。

        聚合网关转发的偶发 5xx / 假 401 会在同一把密钥下随机出现又消失，
        重试一两次通常就能过；400/404 这类配置错误重试没有意义，直接抛出。
        限流（429）另有更长的退避与更多次尝试，见 RATE_LIMIT_*。
        """
        attempt = 0
        while True:
            attempt += 1
            try:
                # model 是本方法的具名参数，不在 call_kwargs 里，必须显式透传。
                return await provider.chat_completion(model=model, **call_kwargs)
            except Exception as exc:
                limit = _attempts_for(exc, attempts)
                if attempt < limit and _is_retryable(exc):
                    delay = _retry_delay(exc, attempt)
                    logger.warning(
                        "LLM call failed on [%s/%s] (attempt %d/%d), retrying in %.1fs: %s",
                        provider_name, model, attempt, limit, delay, exc,
                    )
                    await asyncio.sleep(delay)
                    continue
                raise

    async def _stream_with_cleanup(
        self,
        stream_response: AsyncIterator[str],
        provider: LLMProvider,
    ) -> AsyncIterator[str]:
        try:
            async for chunk in stream_response:
                yield chunk
        finally:
            await self._close_provider_client(provider)

    async def route(
        self,
        task_type: str,
        messages: List[ChatMessage],
        user_id: Optional[UUID] = None,
        stream: bool = False,
        **kwargs
    ) -> Union[ChatResponse, AsyncIterator[str]]:
        temperature_override = kwargs.pop("temperature", None)
        max_tokens_override = kwargs.pop("max_tokens", None)
        require_task_config = kwargs.pop("require_task_config", False)
        timeout_seconds = kwargs.pop("timeout_seconds", None)
        if timeout_seconds is None:
            from app.config import settings
            timeout_seconds = settings.LLM_CHAT_TIMEOUT_SECONDS

        # 1. Fetch active route configs for task_type from database sorted by priority
        async with SessionLocal() as db:
            from sqlalchemy import select, and_
            stmt = (
                select(LLMProviderConfig)
                .where(and_(LLMProviderConfig.task_type == task_type, LLMProviderConfig.enabled == True))
                .order_by(LLMProviderConfig.priority.desc())
            )
            res = await db.execute(stmt)
            route_configs = res.scalars().all()

        from app.config import settings

        # 2. 数据库里配了该任务的通道就用它 —— 管理端「模型配置」页面是唯一入口，
        #    所有任务（含拆题）一视同仁，页面上改完立刻生效。
        if route_configs:
            configs_to_try = [
                {
                    "provider_name": config.provider_name,
                    "model_name": config.model_name,
                    "temperature": 0.7,
                    "max_tokens": 2048,
                    "api_key": decrypt_secret(config.api_key_enc),
                    "base_url": config.base_url
                }
                for config in route_configs
            ]
        # 3. 数据库里没有该任务的通道时才回落 .env。拆题有专用变量，其余任务用通用
        #    SiliconFlow 配置。这里只是首次部署的引导路径，不能反过来盖掉管理端。
        elif task_type == "question_parsing" and settings.QUESTION_PARSING_API_KEY and settings.QUESTION_PARSING_MODEL:
            logger.warning(
                "Task %s has no database channel; falling back to QUESTION_PARSING_* env vars. "
                "Configure it in the admin model settings page to take back control.",
                task_type,
            )
            configs_to_try = [{
                "provider_name": "openai_compatible",
                "model_name": settings.QUESTION_PARSING_MODEL,
                "temperature": 0.2,
                "max_tokens": 8192,
                "api_key": settings.QUESTION_PARSING_API_KEY,
                "base_url": (settings.QUESTION_PARSING_BASE_URL or "").strip().rstrip("/"),
            }]
        else:
            if require_task_config:
                raise RuntimeError(f"No task-specific LLM provider configured. Task: {task_type}")
            sf_key = settings.SILICONFLOW_CHAT_API_KEY or settings.SILICONFLOW_API_KEY
            if not sf_key:
                raise RuntimeError(f"No available LLM provider configured. Task: {task_type}")
            configs_to_try = [{
                "provider_name": "siliconflow",
                "model_name": settings.SILICONFLOW_CHAT_MODEL,
                "temperature": 0.7,
                "max_tokens": 2048,
                "api_key": sf_key,
                "base_url": settings.SILICONFLOW_CHAT_BASE_URL or settings.SILICONFLOW_BASE_URL
            }]

        last_error = None
        for route_config in configs_to_try:
            provider_name = route_config["provider_name"]
            model = route_config["model_name"]
            route_timeout_seconds = timeout_seconds
            
            # Find provider client or instantiate dynamically
            provider = self.providers.get(provider_name)
            should_close_provider = False
            if provider_name in OPENAI_COMPATIBLE_PROVIDERS:
                # Build a fresh client from the selected route config so admin
                # config changes and per-task endpoints take effect immediately.
                from app.core.llm.providers.siliconflow import SiliconFlowProvider
                api_key = route_config.get("api_key")
                base_url = route_config.get("base_url") or PROVIDER_DEFAULT_BASE_URLS.get(provider_name)
                
                # Use environment configuration when DB config does not carry credentials.
                if not api_key:
                    from app.config import settings
                    api_key = settings.SILICONFLOW_CHAT_API_KEY or settings.SILICONFLOW_API_KEY
                    base_url = base_url or settings.SILICONFLOW_CHAT_BASE_URL or settings.SILICONFLOW_BASE_URL
                    route_timeout_seconds = route_timeout_seconds or settings.LLM_CHAT_TIMEOUT_SECONDS
                
                provider = SiliconFlowProvider({
                    "provider_name": provider_name,
                    "api_key": api_key,
                    "base_url": base_url,
                    "timeout_seconds": route_timeout_seconds,
                })
                should_close_provider = True

            if not provider:
                logger.warning(f"LLM Provider {provider_name} is not registered. Skipping.")
                continue

            # Check rate limit rules
            if not await self.rate_limiter.check_limit(provider_name, user_id):
                if should_close_provider:
                    await self._close_provider_client(provider)
                continue

            try:
                start_time = time.monotonic()
                # Run chat completion (同一通道内对网关瞬时错误重试)
                response = await self._chat_with_retry(
                    provider=provider,
                    provider_name=provider_name,
                    model=model,
                    messages=messages,
                    temperature=temperature_override if temperature_override is not None else route_config.get("temperature", 0.7),
                    max_tokens=max_tokens_override if max_tokens_override is not None else route_config.get("max_tokens", 2048),
                    stream=stream,
                    task_type=task_type,
                    **kwargs
                )

                if stream:
                    # For streaming, we yield chunks; logging will record latency separately or log as started
                    await self.usage_logger.log_call(
                        provider=provider_name,
                        model=model,
                        task_type=task_type,
                        user_id=user_id,
                        tokens_in=0,
                        tokens_out=0,
                        latency_ms=(time.monotonic() - start_time) * 1000,
                        status="success"
                    )
                    if should_close_provider:
                        return self._stream_with_cleanup(response, provider)
                    return response

                # Log tokens and latency for block call
                await self.rate_limiter.record_usage(
                    provider_name, user_id, response.usage.get("total_tokens", 0)
                )
                await self.usage_logger.log_call(
                    provider=provider_name,
                    model=model,
                    task_type=task_type,
                    user_id=user_id,
                    tokens_in=response.usage.get("prompt_tokens", 0),
                    tokens_out=response.usage.get("completion_tokens", 0),
                    latency_ms=response.latency_ms,
                    status="success"
                )
                if should_close_provider:
                    await self._close_provider_client(provider)
                return response

            except Exception as e:
                last_error = e
                logger.error(f"LLM Call failed on [{provider_name}/{model}]: {e}", exc_info=True)
                await self.usage_logger.log_call(
                    provider=provider_name,
                    model=model,
                    task_type=task_type,
                    user_id=user_id,
                    tokens_in=0,
                    tokens_out=0,
                    latency_ms=0,
                    status=f"error: {str(e)[:200]}"
                )
                if should_close_provider:
                    await self._close_provider_client(provider)
                continue

        if isinstance(last_error, (TimeoutError, LLMProviderError)):
            raise last_error
        raise RuntimeError(f"No available LLM provider responded. Task: {task_type}. Last Error: {last_error}")
