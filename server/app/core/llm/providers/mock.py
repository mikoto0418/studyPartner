import time
import json
import asyncio
from typing import AsyncIterator, List, Dict, Any, Union
from app.core.llm.base import LLMProvider, ChatMessage, ChatResponse, EmbeddingResponse

class MockProvider(LLMProvider):
    """Mock LLM Provider for local development when SiliconFlow API keys are not set"""

    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(provider_name="mock", config=config or {})

    async def chat_completion(
        self,
        messages: List[ChatMessage],
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        stream: bool = False,
        **kwargs
    ) -> Union[ChatResponse, AsyncIterator[str]]:
        user_message = ""
        for m in reversed(messages):
            if m.role == "user":
                user_message = m.content
                break

        # Get system prompt to understand task or task_type
        system_prompt = ""
        for m in messages:
            if m.role == "system":
                system_prompt = m.content
                break

        task_type = kwargs.get("task_type", "")

        # Generate mock response based on task or content
        if "daily_review" in task_type or "daily_review" in system_prompt:
            content = (
                "## 昨日学习复盘总结\n\n"
                "昨天你在平台上度过了充实的一天。你完成了多项任务，并积极探索了知识库。\n\n"
                "### 学习高光 (Highlights)\n"
                "- 完成了【待办】中的 Transformer 论文核心模块实现。\n"
                "- 在与 AI 助手的交流中，展现了对注意力机制的深入探讨。\n\n"
                "### 潜在关注点 (Concerns)\n"
                "- 有 1 个关于【强化学习】的日程计划被推迟，请合理规划时间。\n\n"
                "### 行动建议 (Suggestions)\n"
                "1. 建议今天优先攻克推迟的强化学习日程。\n"
                "2. 针对注意力机制的多头部分，可以配合可视化代码加深理解。\n\n"
                "### 新增记忆候选 (New Memories Candidate)\n"
                "- 学生对 Transformer 架构理解在加深"
            )
        elif "memory_extract" in task_type or "memory_extract" in system_prompt:
            # Return JSON for extraction
            content = json.dumps([
                {
                    "content": "偏好通过代码实践学习复杂的深度学习模型",
                    "category": "learning_preference",
                    "memory_type": "short_term",
                    "confidence": 0.8,
                    "evidence": "完成了Transformer代码实现，并询问了多头注意力机制"
                }
            ], ensure_ascii=False)
        elif "memory_update" in task_type or "memory_update" in system_prompt:
            # Return JSON for update/conflict detection
            content = json.dumps({
                "conflicts": [],
                "updates": [
                    {
                        "content": "偏好通过代码实践学习复杂的深度学习模型",
                        "category": "learning_preference",
                        "memory_type": "long_term",
                        "confidence": 0.9,
                        "evidence": "再次验证：在 Transformer 模块练习中完全独立实现代码"
                    }
                ]
            }, ensure_ascii=False)
        else:
            content = f"这是一个伴学助手的模拟回复。你刚刚说的是：'{user_message}'。系统已开启伴学助手本地模拟模式（未配置有效的大模型 API Key），在这里你可以正常测试 UI 的流式对话和交互功能！"

        if stream:
            async def chunk_generator() -> AsyncIterator[str]:
                chunk_size = 4
                for i in range(0, len(content), chunk_size):
                    yield content[i:i+chunk_size]
                    await asyncio.sleep(0.05)
            return chunk_generator()

        return ChatResponse(
            content=content,
            model=model,
            provider=self.provider_name,
            usage={"prompt_tokens": len(user_message), "completion_tokens": len(content), "total_tokens": len(user_message) + len(content)},
            finish_reason="stop",
            latency_ms=100
        )

    async def embedding(
        self,
        text: Union[str, List[str]],
        model: str
    ) -> Union[EmbeddingResponse, List[EmbeddingResponse]]:
        input_texts = [text] if isinstance(text, str) else text
        import random
        results = [
            EmbeddingResponse(
                embedding=[random.uniform(-1, 1) for _ in range(1024)],
                model=model,
                provider=self.provider_name,
                usage={"prompt_tokens": len(t), "total_tokens": len(t)}
            )
            for t in input_texts
        ]
        return results[0] if isinstance(text, str) else results

    async def health_check(self) -> bool:
        return True

    async def get_available_models(self) -> List[str]:
        return ["mock-model"]
