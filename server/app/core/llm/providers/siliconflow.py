import time
import json
import httpx
from typing import AsyncIterator, List, Dict, Any, Union

from app.core.llm.base import LLMProvider, ChatMessage, ChatResponse, EmbeddingResponse

class SiliconFlowProvider(LLMProvider):
    """SiliconFlow API integration (compatible with OpenAI format)"""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(provider_name="siliconflow", config=config)
        self.base_url = config.get("base_url", "https://api.siliconflow.cn/v1")
        self.api_key = config.get("api_key", "")
        self.http_client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            },
            timeout=httpx.Timeout(60.0, connect=10.0)
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

        payload = {
            "model": model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": stream,
            **provider_options
        }

        start_time = time.monotonic()

        if stream:
            return self._stream_chat(payload, model, start_time)

        response = await self.http_client.post("/chat/completions", json=payload)
        response.raise_for_status()
        data = response.json()

        latency = (time.monotonic() - start_time) * 1000

        return ChatResponse(
            content=data["choices"][0]["message"]["content"],
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
