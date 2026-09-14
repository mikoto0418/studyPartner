import logging
import re
import uuid
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from sqlalchemy import asc, desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import NotFoundError, ValidationError
from app.models.memory_wiki import MemoryEvent, MemoryLink, MemoryPage, MemoryReviewTask, MemorySource
from app.models.student_memory import DailyReview, StudentMemory

logger = logging.getLogger(__name__)


def slugify(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "-", value)
    value = re.sub(r"-{2,}", "-", value).strip("-")
    return value[:120] or uuid.uuid4().hex[:12]


def _page_simple_dict(page: MemoryPage) -> Dict[str, Any]:
    return {
        "id": str(page.id),
        "slug": page.slug,
        "page_type": page.page_type,
        "title": page.title,
        "summary": page.summary,
        "category": page.category,
        "confidence": page.confidence,
        "status": page.status,
    }


def _similarity(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a.strip().lower(), b.strip().lower()).ratio()


class MemoryWikiService:

    # ---------- Basic CRUD ----------

    @staticmethod
    async def list_pages(
        db: AsyncSession,
        user_id: UUID,
        page: int = 1,
        page_size: int = 20,
        page_type: Optional[str] = None,
        category: Optional[str] = None,
        status: str = "active",
        keyword: Optional[str] = None,
    ) -> Tuple[List[MemoryPage], int]:
        stmt = select(MemoryPage).where(
            MemoryPage.user_id == user_id,
            MemoryPage.deleted_at.is_(None),
        )
        if status:
            stmt = stmt.where(MemoryPage.status == status)
        if page_type:
            stmt = stmt.where(MemoryPage.page_type == page_type)
        if category:
            stmt = stmt.where(MemoryPage.category == category)
        if keyword:
            like = f"%{keyword.strip()}%"
            stmt = stmt.where(
                or_(
                    MemoryPage.title.ilike(like),
                    MemoryPage.summary.ilike(like),
                    MemoryPage.body.ilike(like),
                )
            )

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await db.execute(count_stmt)).scalar() or 0

        stmt = stmt.order_by(desc(MemoryPage.last_reviewed_at), desc(MemoryPage.confidence), desc(MemoryPage.updated_at))
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)
        res = await db.execute(stmt)
        return list(res.scalars().all()), total

    @staticmethod
    async def get_page(
        db: AsyncSession,
        user_id: UUID,
        page_id: UUID,
        load_detail: bool = False,
    ) -> MemoryPage:
        stmt = select(MemoryPage).where(
            MemoryPage.id == page_id,
            MemoryPage.user_id == user_id,
            MemoryPage.deleted_at.is_(None),
        )
        if load_detail:
            stmt = stmt.options(
                selectinload(MemoryPage.sources),
                selectinload(MemoryPage.outbound_links).selectinload(MemoryLink.to_page),
                selectinload(MemoryPage.inbound_links).selectinload(MemoryLink.from_page),
            )
        res = await db.execute(stmt)
        page = res.scalars().first()
        if not page:
            raise NotFoundError("Memory Wiki 页面不存在")
        return page

    @staticmethod
    async def create_page(
        db: AsyncSession,
        user_id: UUID,
        data: Dict[str, Any],
        operator: str = "student",
        review_id: Optional[UUID] = None,
        reason: Optional[str] = None,
    ) -> MemoryPage:
        slug = data.get("slug") or slugify(data.get("title") or "untitled")
        # ensure unique slug per user
        existing = (await db.execute(
            select(MemoryPage).where(MemoryPage.user_id == user_id, MemoryPage.slug == slug, MemoryPage.deleted_at.is_(None))
        )).scalars().first()
        if existing:
            slug = f"{slug}-{uuid.uuid4().hex[:8]}"

        page = MemoryPage(
            id=uuid.uuid4(),
            user_id=user_id,
            slug=slug,
            page_type=data.get("page_type", "concept"),
            title=data.get("title") or "未命名记忆页",
            summary=data.get("summary"),
            body=data.get("body"),
            category=data.get("category", "other"),
            tags=data.get("tags"),
            confidence=float(data.get("confidence", 0.5)),
            status=data.get("status", "active"),
            source_review_id=review_id,
            version=1,
            last_reviewed_at=datetime.now(timezone.utc),
            expires_at=data.get("expires_at"),
            meta=data.get("meta"),
        )
        db.add(page)
        await db.flush()

        db.add(MemoryEvent(
            id=uuid.uuid4(),
            user_id=user_id,
            page_id=page.id,
            action="create",
            before=None,
            after=_page_simple_dict(page),
            reason=reason or "手动创建",
            operator=operator,
            review_id=review_id,
        ))
        await db.commit()
        await db.refresh(page)
        return page

    @staticmethod
    async def update_page(
        db: AsyncSession,
        user_id: UUID,
        page_id: UUID,
        data: Dict[str, Any],
        operator: str = "student",
        reason: Optional[str] = None,
    ) -> MemoryPage:
        page = await MemoryWikiService.get_page(db, user_id, page_id)
        before = _page_simple_dict(page)
        allowed = {"slug", "page_type", "title", "summary", "body", "category", "tags", "confidence", "expires_at", "meta"}
        for field in allowed:
            if field in data:
                setattr(page, field, data[field])
        page.version = (page.version or 1) + 1
        page.last_reviewed_at = datetime.now(timezone.utc)
        db.add(page)

        db.add(MemoryEvent(
            id=uuid.uuid4(),
            user_id=user_id,
            page_id=page.id,
            action="update",
            before=before,
            after=_page_simple_dict(page),
            reason=reason or "手动编辑",
            operator=operator,
        ))
        await db.commit()
        await db.refresh(page)
        return page

    @staticmethod
    async def change_page_status(
        db: AsyncSession,
        user_id: UUID,
        page_id: UUID,
        status: str,
        operator: str = "student",
        reason: Optional[str] = None,
    ) -> MemoryPage:
        page = await MemoryWikiService.get_page(db, user_id, page_id)
        before = _page_simple_dict(page)
        page.status = status
        if status == "archived":
            page.expires_at = datetime.now(timezone.utc)
        db.add(page)

        db.add(MemoryEvent(
            id=uuid.uuid4(),
            user_id=user_id,
            page_id=page.id,
            action="archive" if status == "archived" else "delete",
            before=before,
            after=_page_simple_dict(page),
            reason=reason or f"页面状态变更为 {status}",
            operator=operator,
        ))
        await db.commit()
        await db.refresh(page)
        return page

    # ---------- Sources & Links ----------

    @staticmethod
    async def add_source(
        db: AsyncSession,
        user_id: UUID,
        page_id: UUID,
        data: Dict[str, Any],
        operator: str = "student",
    ) -> MemorySource:
        page = await MemoryWikiService.get_page(db, user_id, page_id)
        source = MemorySource(
            id=uuid.uuid4(),
            page_id=page.id,
            source_type=data.get("source_type", "manual"),
            source_id=data.get("source_id"),
            user_id=user_id,
            occurred_at=data.get("occurred_at") or datetime.now(timezone.utc),
            snippet=data.get("snippet"),
            confidence=float(data.get("confidence", 0.6)),
            meta=data.get("meta"),
        )
        db.add(source)
        page.last_reviewed_at = datetime.now(timezone.utc)
        db.add(page)

        db.add(MemoryEvent(
            id=uuid.uuid4(),
            user_id=user_id,
            page_id=page.id,
            action="update",
            before=None,
            after={"source_added": str(source.id), "source_type": source.source_type},
            reason="新增结构化证据",
            operator=operator,
        ))
        await db.commit()
        await db.refresh(source)
        return source

    @staticmethod
    async def list_sources(
        db: AsyncSession,
        user_id: UUID,
        page_id: UUID,
    ) -> List[MemorySource]:
        page = await MemoryWikiService.get_page(db, user_id, page_id)
        stmt = select(MemorySource).where(MemorySource.page_id == page.id).order_by(desc(MemorySource.occurred_at))
        res = await db.execute(stmt)
        return list(res.scalars().all())

    @staticmethod
    async def add_link(
        db: AsyncSession,
        user_id: UUID,
        page_id: UUID,
        data: Dict[str, Any],
        operator: str = "student",
    ) -> MemoryLink:
        page = await MemoryWikiService.get_page(db, user_id, page_id)
        to_page_id = data.get("to_page_id")
        await MemoryWikiService.get_page(db, user_id, UUID(str(to_page_id)))

        relation = data.get("relation", "related_to")
        strength = float(data.get("strength", 0.5))
        existing = (await db.execute(
            select(MemoryLink).where(
                MemoryLink.user_id == user_id,
                MemoryLink.from_page_id == page.id,
                MemoryLink.to_page_id == to_page_id,
                MemoryLink.relation == relation,
            )
        )).scalars().first()
        if existing:
            existing.strength = strength
            db.add(existing)
            await db.commit()
            await db.refresh(existing)
            return existing

        link = MemoryLink(
            id=uuid.uuid4(),
            user_id=user_id,
            from_page_id=page.id,
            to_page_id=to_page_id,
            relation=relation,
            strength=strength,
        )
        db.add(link)
        page.last_reviewed_at = datetime.now(timezone.utc)
        db.add(page)

        db.add(MemoryEvent(
            id=uuid.uuid4(),
            user_id=user_id,
            page_id=page.id,
            action="update",
            before=None,
            after={"link_added": str(link.id), "to_page_id": str(to_page_id), "relation": relation},
            reason="新增记忆关联",
            operator=operator,
        ))
        await db.commit()
        await db.refresh(link)
        return link

    @staticmethod
    async def list_links(
        db: AsyncSession,
        user_id: UUID,
        page_id: UUID,
    ) -> Tuple[List[MemoryLink], List[MemoryLink]]:
        page = await MemoryWikiService.get_page(db, user_id, page_id)
        out_stmt = select(MemoryLink).where(MemoryLink.from_page_id == page.id)
        in_stmt = select(MemoryLink).where(MemoryLink.to_page_id == page.id)
        return (
            list((await db.execute(out_stmt)).scalars().all()),
            list((await db.execute(in_stmt)).scalars().all()),
        )

    # ---------- Search ----------

    @staticmethod
    async def search_pages(
        db: AsyncSession,
        user_id: UUID,
        query: str = "",
        top_k: int = 10,
        page_type: Optional[str] = None,
        category: Optional[str] = None,
        status: str = "active",
    ) -> List[Tuple[MemoryPage, float]]:
        stmt = select(MemoryPage).where(
            MemoryPage.user_id == user_id,
            MemoryPage.deleted_at.is_(None),
        )
        if status:
            stmt = stmt.where(MemoryPage.status == status)
        if page_type:
            stmt = stmt.where(MemoryPage.page_type == page_type)
        if category:
            stmt = stmt.where(MemoryPage.category == category)

        res = await db.execute(stmt)
        pages = list(res.scalars().all())

        if not pages:
            return []

        query = (query or "").strip().lower()
        scored: List[Tuple[MemoryPage, float]] = []

        now = datetime.now(timezone.utc)
        for page in pages:
            score = 0.0
            if query:
                title = (page.title or "").lower()
                summary = (page.summary or "").lower()
                body = (page.body or "").lower()
                if query in title:
                    score += 0.5
                if query in summary:
                    score += 0.3
                if query in body:
                    score += 0.15
                # token overlap
                query_tokens = set(re.findall(r"[a-z0-9\u4e00-\u9fff]+", query))
                title_tokens = set(re.findall(r"[a-z0-9\u4e00-\u9fff]+", title))
                if query_tokens and title_tokens:
                    score += 0.2 * len(query_tokens & title_tokens) / len(query_tokens)
                if score <= 0:
                    continue
            else:
                # no query -> base score from confidence and recency
                score = 0.5 * page.confidence

            # recency bonus
            if page.last_reviewed_at:
                days = max(0, (now - page.last_reviewed_at).days)
                score += 0.1 * max(0, 1 - days / 30)

            score += 0.1 * page.confidence
            scored.append((page, round(score, 4)))

        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:top_k]

    @staticmethod
    async def build_memory_context(
        db: AsyncSession,
        user_id: UUID,
        query: Optional[str] = None,
        max_pages: int = 8,
    ) -> str:
        hits = await MemoryWikiService.search_pages(db, user_id, query=query or "", top_k=max_pages)
        if not hits:
            return ""

        lines = ["【学生学习画像（Memory Wiki）】"]
        for idx, (page, score) in enumerate(hits, start=1):
            type_zh = {
                "concept": "知识点",
                "entity": "实体",
                "pattern": "学习模式",
                "goal": "目标",
                "weakness": "薄弱点",
                "event": "事件",
            }.get(page.page_type, page.page_type)
            lines.append(
                f"{idx}. [{type_zh}/{page.category}] {page.title} (置信度: {page.confidence:.2f})"
            )
            if page.summary:
                lines.append(f"   - {page.summary}")
        return "\n".join(lines)

    # ---------- Graph ----------

    @staticmethod
    async def get_graph(db: AsyncSession, user_id: UUID) -> Tuple[List[MemoryPage], List[MemoryLink]]:
        pages_stmt = select(MemoryPage).where(
            MemoryPage.user_id == user_id,
            MemoryPage.deleted_at.is_(None),
            MemoryPage.status.in_(["active", "draft"]),
        )
        pages = list((await db.execute(pages_stmt)).scalars().all())
        if pages:
            pages_stmt = select(MemoryLink).where(
                MemoryLink.user_id == user_id,
                MemoryLink.from_page_id.in_([p.id for p in pages]),
                MemoryLink.to_page_id.in_([p.id for p in pages]),
            )
            links = list((await db.execute(pages_stmt)).scalars().all())
        else:
            links = []
        return pages, links

    # ---------- Events & Review Tasks ----------

    @staticmethod
    async def list_events(
        db: AsyncSession,
        user_id: UUID,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[MemoryEvent], int]:
        stmt = select(MemoryEvent).where(MemoryEvent.user_id == user_id)
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await db.execute(count_stmt)).scalar() or 0
        stmt = stmt.order_by(desc(MemoryEvent.created_at))
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)
        res = await db.execute(stmt)
        return list(res.scalars().all()), total

    @staticmethod
    async def create_review_task(
        db: AsyncSession,
        user_id: UUID,
        page_id: Optional[UUID],
        task_type: str,
        payload: Optional[Dict[str, Any]],
        created_by: str = "system",
    ) -> MemoryReviewTask:
        task = MemoryReviewTask(
            id=uuid.uuid4(),
            user_id=user_id,
            page_id=page_id,
            task_type=task_type,
            payload=payload,
            status="pending",
            created_by=created_by,
        )
        db.add(task)
        await db.commit()
        await db.refresh(task)
        return task

    @staticmethod
    async def list_review_tasks(
        db: AsyncSession,
        user_id: UUID,
        status: str = "pending",
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[MemoryReviewTask], int]:
        stmt = select(MemoryReviewTask).where(MemoryReviewTask.user_id == user_id)
        if status:
            stmt = stmt.where(MemoryReviewTask.status == status)
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await db.execute(count_stmt)).scalar() or 0
        stmt = stmt.order_by(desc(MemoryReviewTask.created_at))
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)
        res = await db.execute(stmt)
        return list(res.scalars().all()), total

    @staticmethod
    async def handle_review_task(
        db: AsyncSession,
        user_id: UUID,
        task_id: UUID,
        approve: bool,
        reason: Optional[str] = None,
        operator: str = "student",
    ) -> MemoryReviewTask:
        stmt = select(MemoryReviewTask).where(MemoryReviewTask.id == task_id, MemoryReviewTask.user_id == user_id)
        task = (await db.execute(stmt)).scalars().first()
        if not task:
            raise NotFoundError("确认任务不存在")
        if task.status != "pending":
            raise ValidationError("该确认任务已处理")

        task.status = "approved" if approve else "rejected"
        task.handled_at = datetime.now(timezone.utc)
        task.handled_by = user_id
        task.handled_reason = reason
        db.add(task)

        if task.page_id:
            db.add(MemoryEvent(
                id=uuid.uuid4(),
                user_id=user_id,
                page_id=task.page_id,
                action="confirm" if approve else "reject",
                before=None,
                after={"task_id": str(task.id), "task_type": task.task_type},
                reason=reason or ("学生已确认" if approve else "学生已拒绝"),
                operator=operator,
            ))
        await db.commit()
        await db.refresh(task)
        return task

    # ---------- Lint ----------

    @staticmethod
    async def run_lint(db: AsyncSession, user_id: UUID) -> List[Dict[str, Any]]:
        stmt = select(MemoryPage).where(
            MemoryPage.user_id == user_id,
            MemoryPage.deleted_at.is_(None),
            MemoryPage.status == "active",
        )
        pages = list((await db.execute(stmt)).scalars().all())
        issues: List[Dict[str, Any]] = []

        for page in pages:
            source_count = (await db.execute(
                select(func.count(MemorySource.id)).where(MemorySource.page_id == page.id)
            )).scalar() or 0

            if source_count == 0:
                issues.append({
                    "issue_type": "no_evidence",
                    "page_id": page.id,
                    "title": page.title,
                    "message": "该记忆页没有任何结构化证据",
                    "severity": "warning",
                })
            if page.confidence < 0.3:
                issues.append({
                    "issue_type": "low_confidence",
                    "page_id": page.id,
                    "title": page.title,
                    "message": "记忆置信度过低，建议复核或归档",
                    "severity": "info",
                })
            if page.expires_at and page.expires_at < datetime.now(timezone.utc):
                issues.append({
                    "issue_type": "expired",
                    "page_id": page.id,
                    "title": page.title,
                    "message": "记忆已过期但仍处于 active",
                    "severity": "warning",
                })

        # duplicate detection by title similarity
        for i in range(len(pages)):
            for j in range(i + 1, len(pages)):
                a, b = pages[i], pages[j]
                if _similarity(a.title or "", b.title or "") > 0.88 and a.id != b.id:
                    issues.append({
                        "issue_type": "duplicate",
                        "page_id": a.id,
                        "title": a.title,
                        "message": f"可能和“{b.title}”重复，建议合并",
                        "severity": "warning",
                    })
                    break

        return issues

    @staticmethod
    async def get_stats(db: AsyncSession, user_id: UUID) -> Dict[str, int]:
        total_pages = (await db.execute(
            select(func.count(MemoryPage.id)).where(MemoryPage.user_id == user_id, MemoryPage.deleted_at.is_(None))
        )).scalar() or 0
        active_pages = (await db.execute(
            select(func.count(MemoryPage.id)).where(MemoryPage.user_id == user_id, MemoryPage.status == "active", MemoryPage.deleted_at.is_(None))
        )).scalar() or 0
        source_count = (await db.execute(
            select(func.count(MemorySource.id)).where(MemorySource.user_id == user_id)
        )).scalar() or 0
        link_count = (await db.execute(
            select(func.count(MemoryLink.id)).where(MemoryLink.user_id == user_id)
        )).scalar() or 0
        review_task_count = (await db.execute(
            select(func.count(MemoryReviewTask.id)).where(MemoryReviewTask.user_id == user_id, MemoryReviewTask.status == "pending")
        )).scalar() or 0
        return {
            "total_pages": total_pages,
            "active_pages": active_pages,
            "source_count": source_count,
            "link_count": link_count,
            "review_task_count": review_task_count,
        }

    # ---------- Backfill from Legacy StudentMemory ----------

    @staticmethod
    async def backfill_from_legacy_memories(
        db: AsyncSession,
        user_id: Optional[UUID] = None,
    ) -> Tuple[int, int]:
        """
        Import existing active StudentMemory rows into Memory Wiki as pages + sources + events.
        Returns (created_count, skipped_count). Safe to run multiple times.
        """
        stmt = select(StudentMemory).where(StudentMemory.status == "active")
        if user_id:
            stmt = stmt.where(StudentMemory.user_id == user_id)
        stmt = stmt.order_by(StudentMemory.created_at.asc())

        memories = list((await db.execute(stmt)).scalars().all())
        created = 0
        skipped = 0

        for m in memories:
            # Idempotency check: already migrated legacy memory
            already = (await db.execute(
                select(MemoryPage).where(
                    MemoryPage.user_id == m.user_id,
                    MemoryPage.meta["legacy_memory_id"].astext == str(m.id),
                )
            )).scalars().first()
            if already:
                skipped += 1
                continue

            category = m.category or "other"
            page_type = {
                "learning_preference": "pattern",
                "study_habit": "pattern",
                "interest_area": "goal",
                "goal": "goal",
                "weakness": "weakness",
                "other": "concept",
            }.get(category, "pattern")

            slug = slugify(m.content or m.id.hex)
            used = (await db.execute(
                select(MemoryPage.slug).where(
                    MemoryPage.user_id == m.user_id,
                    MemoryPage.slug == slug,
                    MemoryPage.deleted_at.is_(None),
                )
            )).scalar()
            if used:
                slug = f"{slug}-{uuid.uuid4().hex[:8]}"

            page = MemoryPage(
                id=uuid.uuid4(),
                user_id=m.user_id,
                slug=slug,
                page_type=page_type,
                title=(m.content or "未命名记忆")[:255],
                summary=m.content,
                body=f"## 记忆内容\n\n{m.content or ''}\n\n## 原始证据\n\n{m.evidence or ''}\n",
                category=category,
                tags=None,
                confidence=m.confidence or 0.5,
                status="active",
                source_review_id=m.source_review_id,
                version=m.version or 1,
                last_reviewed_at=m.updated_at or m.created_at or datetime.now(timezone.utc),
                expires_at=m.expires_at,
                meta={
                    "legacy_memory_id": str(m.id),
                    "legacy_memory_type": m.memory_type,
                    "legacy_category": category,
                },
            )
            db.add(page)
            await db.flush()

            if m.evidence:
                db.add(MemorySource(
                    id=uuid.uuid4(),
                    page_id=page.id,
                    source_type="legacy_student_memory",
                    source_id=str(m.id),
                    user_id=m.user_id,
                    occurred_at=m.created_at,
                    snippet=m.evidence,
                    confidence=m.confidence or 0.5,
                    meta={"legacy_memory_id": str(m.id)},
                ))

            db.add(MemoryEvent(
                id=uuid.uuid4(),
                user_id=m.user_id,
                page_id=page.id,
                action="create",
                before=None,
                after={"id": str(page.id), "legacy_memory_id": str(m.id), "title": page.title},
                reason="历史 AI 学情记忆画像迁移至 Memory Wiki",
                operator="system",
                review_id=m.source_review_id,
            ))
            created += 1

        await db.commit()
        return created, skipped

    # ---------- Ingest from Daily Review ----------

    @staticmethod
    async def ingest_daily_review(
        db: AsyncSession,
        user_id: UUID,
        review: DailyReview,
    ) -> List[MemoryPage]:
        """
        Deterministic incremental ingest from a completed daily review.
        For each extracted memory candidate:
          - find similar existing active page by title/content
          - if found: update confidence + append evidence source
          - otherwise: create a new memory page
        """
        created_or_updated: List[MemoryPage] = []
        candidates = review.new_memories or []
        if isinstance(candidates, str):
            try:
                import json
                candidates = json.loads(candidates)
            except Exception:
                candidates = []

        for candidate in candidates:
            if not isinstance(candidate, dict):
                continue
            content = str(candidate.get("content") or "").strip()
            if not content:
                continue

            category = str(candidate.get("category") or "other")
            confidence = float(candidate.get("confidence") or 0.5)
            evidence = str(candidate.get("evidence") or "").strip()
            page_type = "pattern" if category == "study_habit" or category == "learning_preference" else category
            if page_type not in {"concept", "entity", "pattern", "goal", "weakness", "event", "relationship"}:
                page_type = "pattern" if category in {"study_habit", "learning_preference"} else "concept"

            # find by similarity
            similar_page = None
            pages_stmt = select(MemoryPage).where(
                MemoryPage.user_id == user_id,
                MemoryPage.status.in_(["active", "draft"]),
                MemoryPage.deleted_at.is_(None),
            )
            existing_pages = list((await db.execute(pages_stmt)).scalars().all())
            best_sim = 0.85
            for page in existing_pages:
                sim = _similarity(content, page.title or "")
                sim2 = _similarity(content, page.summary or "")
                if max(sim, sim2) > best_sim:
                    best_sim = max(sim, sim2)
                    similar_page = page

            if similar_page:
                old_confidence = similar_page.confidence
                similar_page.confidence = min(1.0, old_confidence + 0.05)
                similar_page.last_reviewed_at = datetime.now(timezone.utc)
                similar_page.version = (similar_page.version or 1) + 1
                similar_page.source_review_id = review.id
                existing_snippet = (await db.execute(
                    select(func.count(MemorySource.id)).where(
                        MemorySource.page_id == similar_page.id,
                        MemorySource.snippet == evidence,
                    )
                )).scalar() or 0
                if evidence and existing_snippet == 0:
                    db.add(MemorySource(
                        id=uuid.uuid4(),
                        page_id=similar_page.id,
                        source_type="daily_review",
                        source_id=str(review.id),
                        user_id=user_id,
                        occurred_at=datetime(review.review_date.year, review.review_date.month, review.review_date.day, tzinfo=timezone.utc),
                        snippet=evidence,
                        confidence=confidence,
                        meta={"review_id": str(review.id)},
                    ))
                db.add(similar_page)
                db.add(MemoryEvent(
                    id=uuid.uuid4(),
                    user_id=user_id,
                    page_id=similar_page.id,
                    action="update",
                    before={"id": str(similar_page.id), "confidence": old_confidence},
                    after={"id": str(similar_page.id), "confidence": similar_page.confidence},
                    reason=f"每日复盘 {review.review_date} 增强证据",
                    operator="system",
                    review_id=review.id,
                ))
                created_or_updated.append(similar_page)
            else:
                slug = slugify(content)
                # ensure uniqueness
                used_slugs = {p.slug for p in existing_pages}
                if slug in used_slugs:
                    slug = f"{slug}-{uuid.uuid4().hex[:8]}"
                page = MemoryPage(
                    id=uuid.uuid4(),
                    user_id=user_id,
                    slug=slug,
                    page_type=page_type,
                    title=content[:255],
                    summary=content,
                    body=f"## 记忆内容\n\n{content}\n",
                    category=category,
                    tags=None,
                    confidence=confidence,
                    status="active",
                    source_review_id=review.id,
                    version=1,
                    last_reviewed_at=datetime.now(timezone.utc),
                )
                db.add(page)
                await db.flush()
                if evidence:
                    db.add(MemorySource(
                        id=uuid.uuid4(),
                        page_id=page.id,
                        source_type="daily_review",
                        source_id=str(review.id),
                        user_id=user_id,
                        occurred_at=datetime(review.review_date.year, review.review_date.month, review.review_date.day, tzinfo=timezone.utc),
                        snippet=evidence,
                        confidence=confidence,
                        meta={"review_id": str(review.id)},
                    ))
                db.add(MemoryEvent(
                    id=uuid.uuid4(),
                    user_id=user_id,
                    page_id=page.id,
                    action="create",
                    before=None,
                    after={"id": str(page.id), "title": page.title},
                    reason=f"每日复盘 {review.review_date} 提取",
                    operator="system",
                    review_id=review.id,
                ))
                created_or_updated.append(page)

        await db.commit()
        for page in created_or_updated:
            await db.refresh(page)
        return created_or_updated