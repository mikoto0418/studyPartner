"""长耗时任务的派发兜底。

生产环境由 docker-compose 里的 sp-worker 消费队列；本地开发经常只起 uvicorn 不起
worker，任务会被静默投进 Redis 再无人消费 —— 表现就是拆题永远停在 pending，
日志里一条错误都没有。所以投递前先探一次 worker 存活，没有 worker 就直接在 API
进程里跑后台任务，保证功能可用、失败可查。
"""

import asyncio
import logging
import time
from typing import Set
from uuid import UUID

logger = logging.getLogger(__name__)

# worker 探活结果缓存，避免每建一份试卷都发一次广播
_PROBE_TTL_SECONDS = 5.0
_probe_state: dict = {"checked_at": 0.0, "alive": False}

# 持有强引用，否则 asyncio 会在任务完成前把它回收掉
_background_tasks: Set[asyncio.Task] = set()


def _probe_workers_sync(timeout: float = 0.5) -> bool:
    from app.core.celery_app import celery_app

    try:
        replies = celery_app.control.ping(timeout=timeout)
    except Exception as exc:  # broker 连不上、超时都算「没有 worker」
        logger.warning("Celery worker probe failed: %s", exc)
        return False
    return bool(replies)


async def workers_alive() -> bool:
    now = time.monotonic()
    if now - _probe_state["checked_at"] < _PROBE_TTL_SECONDS:
        return bool(_probe_state["alive"])

    # control.ping 是阻塞调用，扔到线程里免得卡住事件循环
    alive = await asyncio.to_thread(_probe_workers_sync)
    _probe_state["checked_at"] = now
    _probe_state["alive"] = alive
    if not alive:
        logger.warning(
            "No Celery worker responded; long-running tasks will run inline in the API process."
        )
    return alive


async def _run_inline(paper_id: UUID) -> None:
    from app.core.database import SessionLocal
    from app.services.assessment_service import AssessmentService

    try:
        async with SessionLocal() as db:
            await AssessmentService.run_parse(db, paper_id)
    except Exception as exc:
        logger.error("Inline assessment parse failed for %s: %s", paper_id, exc, exc_info=True)


def _track(task: asyncio.Task) -> None:
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)


async def dispatch_parse_task(paper_id: UUID) -> str:
    """投递拆题任务，返回实际走通的通道（"celery" 或 "inline"）。"""
    if await workers_alive():
        from app.tasks.assessment_tasks import parse_assessment_paper_task

        try:
            parse_assessment_paper_task.delay(str(paper_id))
            return "celery"
        except Exception as exc:
            logger.error(
                "Failed to enqueue assessment parse for %s: %s", paper_id, exc, exc_info=True
            )
            # broker 抖动时退化成进程内执行，别把任务丢进黑洞
            _probe_state["alive"] = False

    _track(asyncio.create_task(_run_inline(paper_id)))
    return "inline"
