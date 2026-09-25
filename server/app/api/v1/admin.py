import time
from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Body, Depends
from sqlalchemy import and_, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_admin
from app.config import settings
from app.core.database import get_db
from app.core.exceptions import ValidationError
from app.core.llm.base import ChatMessage
from app.core.llm.providers.siliconflow import SiliconFlowProvider
from app.core.llm.router import OPENAI_COMPATIBLE_PROVIDERS, PROVIDER_DEFAULT_BASE_URLS
from app.core.security import decrypt_secret, encrypt_secret
from app.models.knowledge import FileModel
from app.models.llm import LLMProviderConfig, LLMUsageLog
from app.models.user import User
from app.schemas.common import BaseResponse
from app.schemas.llm import (
    AdminOverviewOut,
    AdminRuntimeSettingsOut,
    LLMConfigUpsertReq,
    LLMConnectionTestOut,
    LLMConnectionTestReq,
    LLMProviderConfigOut,
    LLMUsageLogOut,
)

router = APIRouter()


def _config_out(config: LLMProviderConfig) -> LLMProviderConfigOut:
    return LLMProviderConfigOut(
        id=config.id,
        provider_name=config.provider_name,
        display_name=config.display_name,
        base_url=config.base_url,
        model_name=config.model_name,
        task_type=config.task_type,
        priority=config.priority,
        enabled=config.enabled,
        rpm_limit=config.rpm_limit,
        tpm_limit=config.tpm_limit,
        has_api_key=bool(config.api_key_enc),
        created_at=config.created_at,
        updated_at=config.updated_at,
    )


def _usage_log_out(log: LLMUsageLog) -> LLMUsageLogOut:
    return LLMUsageLogOut(
        id=log.id,
        task_type=log.task_type,
        model_name=log.model_name,
        total_tokens=int(log.total_tokens or 0),
        latency_ms=log.latency_ms,
        success=log.success,
        error_message=log.error_message,
        created_at=log.created_at,
    )


def _smtp_configured() -> bool:
    required = [
        settings.SMTP_HOST,
        settings.SMTP_USER,
        settings.SMTP_PASSWORD,
        settings.SMTP_FROM_EMAIL,
    ]
    return all(required) and not any(
        item.endswith("@example.com") or item == "password_here"
        for item in required
    )


def _normal_url(value: str | None) -> str:
    return (value or "").strip().rstrip("/")


@router.get("/llm-configs", response_model=BaseResponse[List[LLMProviderConfigOut]], summary="获取 LLM 通道配置")
async def list_llm_configs(
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(LLMProviderConfig).order_by(LLMProviderConfig.task_type.asc(), desc(LLMProviderConfig.priority))
    )
    return BaseResponse.success(data=[_config_out(item) for item in result.scalars().all()], message="获取成功")


@router.put("/llm-configs", response_model=BaseResponse[List[LLMProviderConfigOut]], summary="保存 LLM 通道配置")
async def upsert_llm_configs(
    req: LLMConfigUpsertReq = Body(...),
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    chat_base_url = _normal_url(
        req.chat_base_url
        or req.base_url
        or PROVIDER_DEFAULT_BASE_URLS.get(req.provider_name)
        or settings.SILICONFLOW_CHAT_BASE_URL
        or settings.SILICONFLOW_BASE_URL
    )
    embedding_base_url = _normal_url(
        req.embedding_base_url
        or req.base_url
        or settings.SILICONFLOW_EMBEDDING_BASE_URL
        or settings.SILICONFLOW_BASE_URL
    )
    if not chat_base_url or not embedding_base_url:
        raise ValidationError("对话模型和嵌入模型都必须分别填写 Base URL")

    chat_api_key = req.chat_api_key or req.api_key
    embedding_api_key = req.embedding_api_key or req.api_key
    encrypted_chat_key = encrypt_secret(chat_api_key) if chat_api_key else None
    encrypted_embedding_key = encrypt_secret(embedding_api_key) if embedding_api_key else None

    chat_task_types = [task_type for task_type in req.task_types if task_type != "knowledge_embedding"]
    task_specs = [
        {
            "task_type": task_type,
            "model_name": req.chat_model,
            "base_url": chat_base_url,
            "encrypted_key": encrypted_chat_key,
            "channel_label": "对话模型",
        }
        for task_type in chat_task_types
    ]
    task_specs.append(
        {
            "task_type": "knowledge_embedding",
            "model_name": req.embedding_model,
            "base_url": embedding_base_url,
            "encrypted_key": encrypted_embedding_key,
            "channel_label": "嵌入模型",
        }
    )

    saved: List[LLMProviderConfig] = []
    for priority, spec in enumerate(task_specs):
        existing = (await db.execute(
            select(LLMProviderConfig).where(
                and_(
                    LLMProviderConfig.provider_name == req.provider_name,
                    LLMProviderConfig.task_type == spec["task_type"],
                )
            )
        )).scalars().first()

        if not existing:
            if not spec["encrypted_key"]:
                raise ValidationError(f"首次保存{spec['channel_label']}配置必须填写 API Key")
            existing = LLMProviderConfig(provider_name=req.provider_name, task_type=spec["task_type"])

        existing.display_name = req.display_name
        existing.base_url = spec["base_url"]
        if spec["encrypted_key"]:
            existing.api_key_enc = spec["encrypted_key"]
        if not existing.api_key_enc:
            raise ValidationError(f"{spec['channel_label']}配置缺少 API Key")
        existing.model_name = spec["model_name"]
        existing.priority = len(task_specs) - priority
        existing.enabled = req.enabled
        existing.rpm_limit = req.rpm_limit
        existing.tpm_limit = req.tpm_limit
        db.add(existing)
        saved.append(existing)

    await db.commit()
    for item in saved:
        await db.refresh(item)
    return BaseResponse.success(data=[_config_out(item) for item in saved], message="LLM 配置已保存")


async def _pick_saved_config(
    db: AsyncSession, req: LLMConnectionTestReq
) -> LLMProviderConfig | None:
    """挑出本次要测试的那条已保存通道。

    指定了 task_type 就精确匹配；否则按端点类型在对话/嵌入两组里取优先级最高的一条。
    """
    stmt = select(LLMProviderConfig).where(
        LLMProviderConfig.provider_name == req.provider_name,
        LLMProviderConfig.enabled.is_(True),
    )
    if req.task_type:
        stmt = stmt.where(LLMProviderConfig.task_type == req.task_type)
    elif req.endpoint_type == "embedding":
        stmt = stmt.where(LLMProviderConfig.task_type == "knowledge_embedding")
    else:
        stmt = stmt.where(LLMProviderConfig.task_type != "knowledge_embedding")
    stmt = stmt.order_by(desc(LLMProviderConfig.priority)).limit(1)
    return (await db.execute(stmt)).scalars().first()


@router.post("/llm-configs/test", response_model=BaseResponse[LLMConnectionTestOut], summary="测试 LLM 通道连接")
async def test_llm_connection(
    req: LLMConnectionTestReq = Body(...),
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """连接测试以保存态为准，表单里有值才覆盖。

    表单里的密钥/地址/模型名留空时回落到该通道已保存的配置，所以「测试」本身
    就是对一个完整可用的通道做真实调用，不需要为了点一次按钮重新粘贴明文 Key。
    """
    if req.provider_name not in OPENAI_COMPATIBLE_PROVIDERS:
        raise ValidationError("当前仅支持 OpenAI 兼容通道连接测试")

    saved = await _pick_saved_config(db, req)

    api_key = (req.api_key or "").strip()
    key_source = "form"
    if not api_key:
        if not saved or not saved.api_key_enc:
            raise ValidationError(
                "该通道尚未保存过 API Key，请先填写本次要测试的 Key，或先保存配置"
            )
        api_key = decrypt_secret(saved.api_key_enc)
        if not api_key:
            raise ValidationError("已保存的 API Key 无法解密，请在配置页重新填写并保存")
        key_source = "saved"

    base_url = (
        _normal_url(req.base_url)
        or _normal_url(saved.base_url if saved else None)
        or _normal_url(PROVIDER_DEFAULT_BASE_URLS.get(req.provider_name))
    )
    model_name = (req.model_name or "").strip() or (saved.model_name if saved else "")
    if not model_name:
        raise ValidationError("请填写要测试的模型名，或先保存该通道的模型配置")
    if not base_url:
        raise ValidationError("请填写要测试的 Base URL，或先保存该通道的地址配置")

    provider = SiliconFlowProvider({
        "provider_name": req.provider_name,
        "api_key": api_key,
        "base_url": base_url,
    })
    started = time.monotonic()
    try:
        if req.endpoint_type == "embedding":
            embedding = await provider.embedding("连接测试", model_name)
            ok = bool(getattr(embedding, "embedding", None))
        else:
            await provider.chat_completion(
                messages=[ChatMessage(role="user", content="请只回复 OK，不要解释。")],
                model=model_name,
                temperature=0,
                max_tokens=256,
                stream=False,
            )
            ok = True
    except Exception as exc:
        raise ValidationError(f"模型通道连接测试失败：{str(exc)[:160]}") from exc
    finally:
        await provider.http_client.aclose()

    latency_ms = int((time.monotonic() - started) * 1000)
    if not ok:
        raise ValidationError("模型通道连接测试失败，请检查 Base URL、API Key 和模型名")
    return BaseResponse.success(
        data=LLMConnectionTestOut(
            provider_name=req.provider_name,
            model_name=model_name,
            latency_ms=latency_ms,
            ok=True,
            key_source=key_source,
        ),
        message="连接测试成功",
    )

@router.get("/overview", response_model=BaseResponse[AdminOverviewOut], summary="管理面板概览统计")
async def get_admin_overview(
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    today = datetime.now(timezone.utc).date()
    start_dt = datetime(today.year, today.month, today.day, tzinfo=timezone.utc)

    total_users = int((await db.execute(select(func.count(User.id)).where(User.deleted_at.is_(None)))).scalar() or 0)
    llm_calls_today = int((await db.execute(
        select(func.count(LLMUsageLog.id)).where(LLMUsageLog.created_at >= start_dt)
    )).scalar() or 0)
    storage_bytes = int((await db.execute(
        select(func.coalesce(func.sum(FileModel.file_size), 0)).where(FileModel.deleted_at.is_(None))
    )).scalar() or 0)
    logs = list((await db.execute(
        select(LLMUsageLog).order_by(desc(LLMUsageLog.created_at)).limit(10)
    )).scalars().all())

    return BaseResponse.success(
        data=AdminOverviewOut(
            total_users=total_users,
            llm_calls_today=llm_calls_today,
            storage_bytes=storage_bytes,
            service_status="healthy",
            recent_usage_logs=[_usage_log_out(log) for log in logs],
        ),
        message="获取成功",
    )


@router.get("/settings", response_model=BaseResponse[AdminRuntimeSettingsOut], summary="管理面板运行配置摘要")
async def get_admin_settings(
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    provider_count = int((await db.execute(select(func.count(LLMProviderConfig.id)))).scalar() or 0)
    enabled_provider_count = int((await db.execute(
        select(func.count(LLMProviderConfig.id)).where(LLMProviderConfig.enabled.is_(True))
    )).scalar() or 0)

    return BaseResponse.success(
        data=AdminRuntimeSettingsOut(
            app_env=settings.APP_ENV,
            app_debug=settings.APP_DEBUG,
            inline_scheduler_enabled=settings.ENABLE_INLINE_SCHEDULER,
            smtp_configured=_smtp_configured(),
            smtp_host=settings.SMTP_HOST,
            smtp_from_email=settings.SMTP_FROM_EMAIL or None,
            minio_endpoint=settings.MINIO_ENDPOINT,
            minio_bucket_name=settings.MINIO_BUCKET_NAME,
            qdrant_endpoint=f"{settings.QDRANT_HOST}:{settings.QDRANT_PORT}",
            llm_provider_count=provider_count,
            enabled_llm_provider_count=enabled_provider_count,
        ),
        message="获取成功",
    )
