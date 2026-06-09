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
from app.core.llm.providers.siliconflow import SiliconFlowProvider
from app.core.security import encrypt_secret
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
    encrypted_key = encrypt_secret(req.api_key) if req.api_key else None
    task_model_pairs = [(task_type, req.chat_model) for task_type in req.task_types]
    task_model_pairs.append(("knowledge_embedding", req.embedding_model))

    saved: List[LLMProviderConfig] = []
    for priority, (task_type, model_name) in enumerate(task_model_pairs):
        existing = (await db.execute(
            select(LLMProviderConfig).where(
                and_(
                    LLMProviderConfig.provider_name == req.provider_name,
                    LLMProviderConfig.task_type == task_type,
                )
            )
        )).scalars().first()
        if not existing:
            if not encrypted_key:
                raise ValidationError("首次保存 LLM 配置必须填写 API Key")
            existing = LLMProviderConfig(provider_name=req.provider_name, task_type=task_type)
        existing.display_name = req.display_name
        existing.base_url = req.base_url
        if encrypted_key:
            existing.api_key_enc = encrypted_key
        existing.model_name = model_name
        existing.priority = len(task_model_pairs) - priority
        existing.enabled = req.enabled
        existing.rpm_limit = req.rpm_limit
        existing.tpm_limit = req.tpm_limit
        db.add(existing)
        saved.append(existing)

    await db.commit()
    for item in saved:
        await db.refresh(item)
    return BaseResponse.success(data=[_config_out(item) for item in saved], message="LLM 配置已保存")


@router.post("/llm-configs/test", response_model=BaseResponse[LLMConnectionTestOut], summary="测试 LLM 网关连接")
async def test_llm_connection(
    req: LLMConnectionTestReq = Body(...),
    current_user: User = Depends(require_admin),
):
    if req.provider_name != "siliconflow":
        raise ValidationError("当前仅支持 SiliconFlow 连接测试")
    provider = SiliconFlowProvider({"api_key": req.api_key, "base_url": req.base_url})
    started = time.monotonic()
    ok = await provider.health_check()
    latency_ms = int((time.monotonic() - started) * 1000)
    if not ok:
        raise ValidationError("LLM 网关连接测试失败，请检查 Base URL 与 API Key")
    return BaseResponse.success(
        data=LLMConnectionTestOut(
            provider_name=req.provider_name,
            model_name=req.model_name,
            latency_ms=latency_ms,
            ok=True,
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
