import os
import sys
import asyncio

import pytest

sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "server"))

from app.config import settings
from app.core.exceptions import ValidationError
from app.core.llm.base import ChatMessage
from app.core.llm.router import LLMRouter
from app.services.email_service import EmailService
from app.services.knowledge_service import get_embedding


class _EmptyScalars:
    def all(self):
        return []

    def first(self):
        return None


class _EmptyResult:
    def scalars(self):
        return _EmptyScalars()


class _EmptyAsyncSession:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def execute(self, _stmt):
        return _EmptyResult()

    def add(self, _item):
        pass

    async def commit(self):
        pass


def test_email_service_fails_when_smtp_is_not_configured(monkeypatch):
    monkeypatch.setattr(settings, "SMTP_HOST", "")
    monkeypatch.setattr(settings, "SMTP_USER", "")
    monkeypatch.setattr(settings, "SMTP_PASSWORD", "")
    monkeypatch.setattr(settings, "SMTP_FROM_EMAIL", "")

    with pytest.raises(ValidationError, match="SMTP"):
        asyncio.run(EmailService.send_verification_code("student@example.com", "123456"))


def test_embedding_fails_when_provider_key_is_missing(monkeypatch):
    monkeypatch.setattr(settings, "SILICONFLOW_API_KEY", "")
    monkeypatch.setattr("app.services.knowledge_service.SessionLocal", lambda: _EmptyAsyncSession())

    with pytest.raises(ValidationError, match="Embedding"):
        asyncio.run(get_embedding("需要生成真实向量的文本"))


def test_llm_router_fails_without_configured_provider(monkeypatch):
    monkeypatch.setattr(settings, "SILICONFLOW_API_KEY", "")
    monkeypatch.setattr("app.core.llm.router.SessionLocal", lambda: _EmptyAsyncSession())

    router = LLMRouter(providers={})

    with pytest.raises(RuntimeError, match="No available LLM provider"):
        asyncio.run(
            router.route(
                task_type="student_chat",
                messages=[ChatMessage(role="user", content="你好")],
                stream=False,
            )
        )
