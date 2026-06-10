import time
import logging
from typing import Optional, List, Dict, Any, Union, AsyncIterator
from uuid import UUID

from app.core.database import SessionLocal
from app.models.llm import LLMUsageLog, LLMProviderConfig
from app.core.llm.base import LLMProvider, ChatMessage, ChatResponse
from app.core.security import decrypt_secret

logger = logging.getLogger(__name__)
OPENAI_COMPATIBLE_PROVIDERS = {"siliconflow", "xiaomi", "xiaomi_token_plan", "openai_compatible"}

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

        # 2. Use explicit environment configuration if no provider config exists in the database.
        if not route_configs:
            if require_task_config:
                raise RuntimeError(f"No task-specific LLM provider configured. Task: {task_type}")
            from app.config import settings
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
        else:
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

        last_error = None
        for route_config in configs_to_try:
            provider_name = route_config["provider_name"]
            model = route_config["model_name"]
            
            # Find provider client or instantiate dynamically
            provider = self.providers.get(provider_name)
            should_close_provider = False
            if provider_name in OPENAI_COMPATIBLE_PROVIDERS:
                # Build a fresh client from the selected route config so admin
                # config changes and per-task endpoints take effect immediately.
                from app.core.llm.providers.siliconflow import SiliconFlowProvider
                api_key = route_config.get("api_key")
                base_url = route_config.get("base_url")
                
                # Use environment configuration when DB config does not carry credentials.
                if not api_key:
                    from app.config import settings
                    api_key = settings.SILICONFLOW_CHAT_API_KEY or settings.SILICONFLOW_API_KEY
                    base_url = base_url or settings.SILICONFLOW_CHAT_BASE_URL or settings.SILICONFLOW_BASE_URL
                
                provider = SiliconFlowProvider({
                    "provider_name": provider_name,
                    "api_key": api_key,
                    "base_url": base_url,
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
                # Run chat completion
                response = await provider.chat_completion(
                    messages=messages,
                    model=model,
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

        raise RuntimeError(f"No available LLM provider responded. Task: {task_type}. Last Error: {last_error}")
