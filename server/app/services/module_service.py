from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.module import FeatureModule

MODULE_REGISTRY: List[Dict[str, Any]] = [
    {"code": "assessment", "name": "在线作业/考试", "description": "发题工作台与学生做题", "roles": ["teacher", "student"]},
    {"code": "memory", "name": "记忆 Wiki", "description": "学生知识记忆标签体系", "roles": ["student"]},
    {"code": "ai_chat", "name": "AI 伴学", "description": "AI 对话助手", "roles": ["student"]},
    {"code": "calendar", "name": "月历计划", "description": "学习计划月历", "roles": ["student"]},
    {"code": "knowledge", "name": "知识库", "description": "实验室知识库", "roles": ["student"]},
    {"code": "bilibili", "name": "B站学习", "description": "B站视频学习室", "roles": ["student"]},
    {"code": "learning_path", "name": "学习路径", "description": "学习路径规划", "roles": ["teacher", "student"]},
    {"code": "growth", "name": "成长全览", "description": "成长数据看板", "roles": ["student"]},
    {"code": "tasks", "name": "任务管理", "description": "学习任务发布", "roles": ["teacher"]},
    {"code": "classes", "name": "班级看板", "description": "班级学情看板", "roles": ["teacher"]},
    {"code": "announcements", "name": "公告", "description": "公告发布与接收", "roles": ["teacher", "admin"]},
]


class ModuleService:
    @staticmethod
    def _primary_role(role_codes) -> str:
        codes = list(role_codes or [])
        if "admin" in codes:
            return "admin"
        if "teacher" in codes:
            return "teacher"
        return "student"

    @staticmethod
    async def sync_modules(db: AsyncSession) -> None:
        result = await db.execute(select(FeatureModule))
        existing = {m.code: m for m in result.unique().scalars().all()}

        missing = [
            {
                "code": item["code"],
                "name": item["name"],
                "description": item.get("description"),
                "roles": item["roles"],
                "enabled": True,
                "visible": True,
            }
            for item in MODULE_REGISTRY
            if item["code"] not in existing
        ]
        dirty = False
        for item in MODULE_REGISTRY:
            m = existing.get(item["code"])
            if m is None:
                continue
            if m.name != item["name"]:
                m.name = item["name"]
                dirty = True
            if m.roles != item["roles"]:
                m.roles = item["roles"]
                dirty = True

        if not missing and not dirty:
            # 读路径无写入，避免 GET 触发写事务与并发唯一约束冲突
            return

        if missing:
            # 并发下另一个请求可能已插入同样的 code，交给 ON CONFLICT 兜底
            await db.execute(
                pg_insert(FeatureModule).values(missing).on_conflict_do_nothing(
                    index_elements=["code"]
                )
            )
        await db.commit()

    @staticmethod
    async def _rows_by_code(db: AsyncSession) -> Dict[str, FeatureModule]:
        result = await db.execute(select(FeatureModule))
        return {m.code: m for m in result.unique().scalars().all()}

    @staticmethod
    def _to_dict(item: Dict[str, Any], m: Optional[FeatureModule]) -> Dict[str, Any]:
        return {
            "code": item["code"],
            "name": item["name"],
            "description": item.get("description"),
            "enabled": m.enabled if m else True,
            "visible": m.visible if m else True,
        }

    @staticmethod
    async def list_for_role(db: AsyncSession, role: str) -> List[Dict[str, Any]]:
        await ModuleService.sync_modules(db)
        rows = await ModuleService._rows_by_code(db)
        out: List[Dict[str, Any]] = []
        for item in MODULE_REGISTRY:
            if role not in (item.get("roles") or []):
                continue
            out.append(ModuleService._to_dict(item, rows.get(item["code"])))
        return out

    @staticmethod
    async def list_all(db: AsyncSession) -> List[Dict[str, Any]]:
        await ModuleService.sync_modules(db)
        rows = await ModuleService._rows_by_code(db)
        return [ModuleService._to_dict(item, rows.get(item["code"])) for item in MODULE_REGISTRY]

    @staticmethod
    async def update_module(
        db: AsyncSession,
        code: str,
        enabled: Optional[bool],
        visible: Optional[bool],
    ) -> Dict[str, Any]:
        await ModuleService.sync_modules(db)
        result = await db.execute(select(FeatureModule).where(FeatureModule.code == code))
        m = result.scalars().first()
        if m is None:
            raise KeyError(code)
        if enabled is not None:
            m.enabled = enabled
        if visible is not None:
            m.visible = visible
        await db.commit()
        await db.refresh(m)
        return {"code": m.code, "name": m.name, "description": m.description, "enabled": m.enabled, "visible": m.visible}