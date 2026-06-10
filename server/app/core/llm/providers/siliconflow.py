import time
import json
import httpx
from typing import AsyncIterator, List, Dict, Any, Union

from app.core.llm.base import LLMProvider, ChatMessage, ChatResponse, EmbeddingResponse, LLMProviderError

class SiliconFlowProvider(LLMProvider):
    """OpenAI-compatible chat and embedding provider."""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(provider_name=config.get("provider_name", "siliconflow"), config=config)
        self.base_url = config.get("base_url", "https://api.siliconflow.cn/v1")
        self.api_key = config.get("api_key", "")
        timeout_seconds = float(config.get("timeout_seconds") or 60.0)
        self.is_xiaomi_token_plan = "xiaomimimo.com" in self.base_url.lower()
        headers = {"Content-Type": "application/json"}
        if self.is_xiaomi_token_plan:
            headers["api-key"] = self.api_key
        else:
            headers["Authorization"] = f"Bearer {self.api_key}"
        self.http_client = httpx.AsyncClient(
            base_url=self.base_url,
            headers=headers,
            timeout=httpx.Timeout(timeout_seconds, connect=min(10.0, timeout_seconds))
        )

    async def chat_completion(
        self,
        messages: List[ChatMessage],
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        stream: bool = False,
        **kwargs
    ) -> Union[ChatResponse, AsyncIterator[str]]:
        # Keep router-only metadata out of the provider payload. SiliconFlow uses
        # the OpenAI-compatible schema and may reject unknown fields such as task_type.
        provider_options = dict(kwargs)
        provider_options.pop("task_type", None)
        provider_options.pop("max_tokens", None)
        provider_options.pop("max_completion_tokens", None)
        token_field = "max_completion_tokens" if self.is_xiaomi_token_plan else "max_tokens"
        if self.is_xiaomi_token_plan and "thinking" not in provider_options:
            provider_options["thinking"] = {"type": "disabled"}

        payload = {
            "model": model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "temperature": temperature,
            token_field: max_tokens,
            "stream": stream,
            **provider_options
        }

        start_time = time.monotonic()

        if stream:
            return self._stream_chat(payload, model, start_time)

        try:
            response = await self.http_client.post("/chat/completions", json=payload)
        except httpx.TimeoutException as exc:
            raise TimeoutError(
                f"{self.provider_name} 模型响应超时，请检查模型服务状态或在管理员模型配置中换用响应更快的模型。"
            ) from exc
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise LLMProviderError(self._http_error_message(exc.response)) from exc
        data = response.json()

        latency = (time.monotonic() - start_time) * 1000

        message = data["choices"][0].get("message", {})

        return ChatResponse(
            content=message.get("content") or "",
            model=data.get("model", model),
            provider=self.provider_name,
            usage=data.get("usage", {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}),
            finish_reason=data["choices"][0].get("finish_reason", "stop"),
            latency_ms=latency
        )

    async def _stream_chat(
        self, payload: Dict[str, Any], model: str, start_time: float
    ) -> AsyncIterator[str]:
        async with self.http_client.stream("POST", "/chat/completions", json=payload) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if line.startswith("data: "):
                    chunk = line[6:].strip()
                    if not chunk:
                        continue
                    if chunk == "[DONE]":
                        break
                    try:
                        data = json.loads(chunk)
                        delta = data["choices"][0].get("delta", {})
                        if "content" in delta and delta["content"]:
                            yield delta["content"]
                    except Exception:
                        pass

    async def embedding(
        self,
        text: Union[str, List[str]],
        model: str
    ) -> Union[EmbeddingResponse, List[EmbeddingResponse]]:
        input_texts = [text] if isinstance(text, str) else text
        payload = {
            "model": model,
            "input": input_texts
        }

        response = await self.http_client.post("/embeddings", json=payload)
        response.raise_for_status()
        data = response.json()

        results = [
            EmbeddingResponse(
                embedding=item["embedding"],
                model=data.get("model", model),
                provider=self.provider_name,
                usage=data.get("usage", {"prompt_tokens": 0, "total_tokens": 0})
            )
            for item in data["data"]
        ]

        return results[0] if isinstance(text, str) else results

    async def health_check(self) -> bool:
        try:
            response = await self.http_client.get("/models")
            return response.status_code == 200
        except Exception:
            return False

    async def get_available_models(self) -> List[str]:
        response = await self.http_client.get("/models")
        response.raise_for_status()
        data = response.json()
        return [m["id"] for m in data.get("data", [])]

    def _http_error_message(self, response: httpx.Response) -> str:
        detail = ""
        try:
            data = response.json()
            if isinstance(data, dict):
                error = data.get("error") or data
                if isinstance(error, dict):
                    detail = error.get("message") or error.get("detail") or json.dumps(error, ensure_ascii=False)
                else:
                    detail = str(error)
        except Exception:
            detail = response.text[:500]

        if response.status_code == 429:
            reason = "模型服务限流或订阅额度暂时不可用"
        elif response.status_code in {401, 403}:
            reason = "模型 API Key 无效或权限不足"
        elif response.status_code == 400:
            reason = "模型请求参数不兼容"
        else:
            reason = f"模型服务返回 HTTP {response.status_code}"
        return f"{self.provider_name} {reason}。{detail}".strip()
