import asyncio
import io
import json
import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import delete, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, PermissionDenied, ValidationError
from app.core.redis import redis_client
from app.models.assessment import (
    AssessmentAnswer,
    AssessmentAttempt,
    AssessmentPaper,
    AssessmentQuestion,
    BehaviorEvent,
)
from app.models.knowledge import FileModel
from app.models.learning_path import ClassGroup, ClassMember
from app.models.user import StudentProfile, User
from app.services.minio_service import MinioService
from app.services import question_parser as question_parser_module
from app.utils.parser import extract_images, parse_document

IMG_RE = re.compile(r"\[\[IMG:(\d+)\]\]")

logger = logging.getLogger(__name__)

# 与前端 useAntiCheat({ maxFullscreenExits: 3 }) 保持一致
FULLSCREEN_EXIT_LIMIT = 3


class AssessmentService:
    @staticmethod
    def _progress_key(paper_id: UUID) -> str:
        return f"assessment:parse:{paper_id}"

    @staticmethod
    async def set_parse_progress(paper_id: UUID, progress: Dict[str, Any]) -> None:
        await redis_client.set(
            AssessmentService._progress_key(paper_id),
            json.dumps(progress, ensure_ascii=False),
            ex=86400,
        )

    @staticmethod
    async def get_parse_progress(paper_id: UUID) -> Optional[Dict[str, Any]]:
        raw = await redis_client.get(AssessmentService._progress_key(paper_id))
        return json.loads(raw) if raw else None

    @staticmethod
    async def create_paper(
        db: AsyncSession,
        teacher_id: UUID,
        file_id: UUID,
        title: str,
        description: Optional[str] = None,
    ) -> AssessmentPaper:
        file = (
            await db.execute(
                select(FileModel).where(FileModel.id == file_id, FileModel.deleted_at.is_(None))
            )
        ).scalars().first()
        if not file:
            raise NotFoundError("上传文件不存在")
        if file.uploader_id != teacher_id:
            raise PermissionDenied("无权使用该文件创建试卷")

        paper = AssessmentPaper(
            creator_id=teacher_id,
            title=title,
            description=description,
            source_file_id=file_id,
            parse_status="pending",
        )
        db.add(paper)
        await db.commit()
        await db.refresh(paper)

        from app.tasks.assessment_tasks import parse_assessment_paper_task

        parse_assessment_paper_task.delay(str(paper.id))
        await AssessmentService.set_parse_progress(paper.id, {"stage": "pending", "total": 0, "done": 0})
        return paper

    @staticmethod
    async def get_paper(db: AsyncSession, paper_id: UUID, teacher_id: UUID) -> AssessmentPaper:
        paper = (
            await db.execute(
                select(AssessmentPaper).where(
                    AssessmentPaper.id == paper_id,
                    AssessmentPaper.deleted_at.is_(None),
                )
            )
        ).scalars().first()
        if not paper or paper.creator_id != teacher_id:
            raise NotFoundError("试卷不存在")
        return paper

    @staticmethod
    async def list_papers(db: AsyncSession, teacher_id: UUID) -> List[AssessmentPaper]:
        result = await db.execute(
            select(AssessmentPaper)
            .where(AssessmentPaper.creator_id == teacher_id, AssessmentPaper.deleted_at.is_(None))
            .order_by(AssessmentPaper.created_at.desc())
        )
        return list(result.scalars().all())

    @staticmethod
    async def list_questions(db: AsyncSession, paper_id: UUID, teacher_id: UUID) -> List[AssessmentQuestion]:
        await AssessmentService.get_paper(db, paper_id, teacher_id)
        result = await db.execute(
            select(AssessmentQuestion)
            .where(AssessmentQuestion.paper_id == paper_id)
            .order_by(AssessmentQuestion.order_index.asc())
        )
        return list(result.scalars().all())

    @staticmethod
    async def save_questions(
        db: AsyncSession,
        paper_id: UUID,
        teacher_id: UUID,
        questions: List[Dict[str, Any]],
    ) -> AssessmentPaper:
        paper = await AssessmentService.get_paper(db, paper_id, teacher_id)
        # 整表重建会级联删除 assessment_answers，因此只允许在尚未发布的状态下重建。
        # 注意：发布是不可逆的（没有撤回接口），错误信息不要指向不存在的操作。
        if paper.parse_status == "published":
            raise ValidationError("该试卷已发布，发布后不可再修改题目")
        if paper.parse_status == "parsing":
            raise ValidationError("试卷正在解析中，请等待解析完成后再校对")
        if paper.parse_status not in ("awaiting_review", "publish_failed", "failed"):
            raise ValidationError(f"当前状态（{paper.parse_status}）不可保存题目")

        # 整表重建会级联删除 assessment_answers（question_id 为 ON DELETE CASCADE），
        # 已有作答时禁止重建，避免静默清空学生答案。
        answered = await db.execute(
            select(func.count(AssessmentAnswer.id)).where(
                AssessmentAnswer.question_id.in_(
                    select(AssessmentQuestion.id).where(AssessmentQuestion.paper_id == paper_id)
                )
            )
        )
        if (answered.scalar() or 0) > 0:
            raise ValidationError("该试卷已有学生作答，禁止重建题目")

        await db.execute(delete(AssessmentQuestion).where(AssessmentQuestion.paper_id == paper_id))

        total_score = 0.0
        for index, q in enumerate(questions):
            question_type = q.get("question_type") or "short"
            score = float(q.get("score") or 0.0)
            total_score += score
            db.add(
                AssessmentQuestion(
                    paper_id=paper_id,
                    order_index=index,
                    question_type=question_type,
                    stem=(q.get("stem") or "").strip(),
                    stem_images=q.get("stem_images") or None,
                    options=q.get("options") or None,
                    answer=q.get("answer"),
                    analysis=q.get("analysis"),
                    score=score,
                    difficulty=q.get("difficulty"),
                    tags=q.get("tags") or None,
                    source_chunk=q.get("source_chunk"),
                )
            )

        paper.question_count = len(questions)
        paper.total_score = total_score
        paper.parse_status = "awaiting_review"
        # 回到「待发布」必须清掉预约时间：否则 beat 会按残留的 publish_at
        # 自动发布，教师拿到一份没点过发布的试卷（失败时存的还是未解析的
        # raw_target，里面没有 due_at，截止时间被静默丢弃）。
        # publish_target / parse_error 保留：前端「重新发送」要靠它们回填
        # 上次的发布对象与失败原因。
        paper.publish_at = None
        paper.published_at = None
        await db.commit()
        await db.refresh(paper)
        return paper

    @staticmethod
    async def publish_paper(
        db: AsyncSession,
        paper_id: UUID,
        teacher_id: UUID,
        publish_target: Dict[str, Any],
        publish_at: Optional[datetime] = None,
        due_at: Optional[datetime] = None,
    ) -> AssessmentPaper:
        paper = await AssessmentService.get_paper(db, paper_id, teacher_id)
        if paper.parse_status not in ("awaiting_review", "publish_failed"):
            raise ValidationError("仅完成人工校对的试卷可发布")

        raw_target = dict(publish_target or {})
        if not raw_target:
            raise ValidationError("发布对象不能为空")

        target = dict(raw_target)
        try:
            whitelist = await AssessmentService._resolve_student_identifiers(
                db, target.get("whitelist") or [], teacher_id
            )
            blacklist = await AssessmentService._resolve_student_identifiers(
                db, target.get("blacklist") or [], teacher_id
            )
            subset = await AssessmentService._resolve_student_identifiers(
                db, target.get("student_ids") or [], teacher_id
            )

            if whitelist:
                target["whitelist"] = whitelist
            else:
                target.pop("whitelist", None)
            if blacklist:
                target["blacklist"] = blacklist
            else:
                target.pop("blacklist", None)
            # 解析为空说明这些学生全都不在当前教师班内，必须 pop 掉：
            # 保留原始值的话 _is_targeted 会拿未解析的 ID 做字符串比对，
            # 把试卷发给其他教师班级的学生。
            if subset:
                target["student_ids"] = subset
            else:
                target.pop("student_ids", None)

            ttype = str(target.get("type") or "").strip()
            if ttype == "student":
                resolved_ids = await AssessmentService._resolve_student_identifiers(
                    db, target.get("ids") or [], teacher_id
                )
                if not resolved_ids:
                    raise ValidationError("未匹配到任何有效学生，请检查学号 / 用户名 / 学生 ID")
                target["ids"] = resolved_ids
            elif ttype == "class":
                raw_class_ids = AssessmentService._to_uuid_list(target.get("ids") or [])
                if not raw_class_ids:
                    raise ValidationError("请至少选择一个班级")
                # 只允许发布到自己名下的班级：否则可把试卷投给其他教师班级的学生
                owned = await db.execute(
                    select(ClassGroup.id).where(
                        ClassGroup.id.in_(raw_class_ids),
                        ClassGroup.teacher_id == teacher_id,
                    )
                )
                owned_ids = {str(cid) for cid in owned.scalars().all()}
                if len(owned_ids) != len({str(c) for c in raw_class_ids}):
                    raise ValidationError("选择的班级不属于当前教师")
                target["ids"] = [str(c) for c in raw_class_ids]
            else:
                # 后端只有 class / student 两种发布对象；未知类型必须拒绝，
                # 否则会「发布成功」但没有任何学生能命中（_is_targeted 不认）。
                raise ValidationError(f"不支持的发布对象类型：{ttype or '空'}")
        except ValidationError as e:
            paper.publish_target = raw_target
            paper.publish_at = publish_at
            paper.parse_status = "publish_failed"
            paper.parse_error = e.message or "发布失败"
            await db.commit()
            await db.refresh(paper)
            raise
        except (TypeError, ValueError):
            # publish_target 是自由 dict，内层值没有 schema 校验。解析途中出现
            # 未预期的类型错误时也要落到 publish_failed，而不是冒到全局变成 500。
            paper.publish_target = raw_target
            paper.publish_at = publish_at
            paper.parse_status = "publish_failed"
            paper.parse_error = "发布对象格式不正确"
            await db.commit()
            await db.refresh(paper)
            raise ValidationError("发布对象格式不正确")

        if due_at is not None:
            target["due_at"] = due_at.isoformat()

        paper.publish_target = target
        paper.publish_at = publish_at
        paper.parse_error = None
        if publish_at is None:
            paper.published_at = datetime.now(timezone.utc)
            paper.parse_status = "published"
        else:
            paper.parse_status = "awaiting_review"

        await db.commit()
        await db.refresh(paper)
        return paper

    @staticmethod
    async def publish_due_papers(db: AsyncSession) -> int:
        now = datetime.now(timezone.utc)
        result = await db.execute(
            select(AssessmentPaper)
            .where(
                AssessmentPaper.parse_status == "awaiting_review",
                AssessmentPaper.publish_at.is_not(None),
                AssessmentPaper.publish_at <= now,
                AssessmentPaper.deleted_at.is_(None),
            )
            .with_for_update(skip_locked=True)
        )
        papers = result.scalars().all()
        for paper in papers:
            paper.parse_status = "published"
            paper.published_at = now
        if papers:
            await db.commit()
        return len(papers)

    @staticmethod
    async def finalize_expired_attempts(db: AsyncSession, limit: int = 200) -> int:
        """把已过截止时间、仍停在 in_progress 的作答按已存答案结算。

        学生开考后直接关掉浏览器且不再回来时，attempt 永远停在 in_progress：
        教师端看不到「待批改」，学生本人不重进页面也不会被结算，这份作答就
        永久卡住。截止时间一过就必须由服务端收卷。
        """
        now = datetime.now(timezone.utc)
        result = await db.execute(
            select(AssessmentAttempt, AssessmentPaper)
            .join(AssessmentPaper, AssessmentPaper.id == AssessmentAttempt.paper_id)
            .where(
                AssessmentAttempt.status == "in_progress",
                AssessmentPaper.parse_status == "published",
                AssessmentPaper.deleted_at.is_(None),
            )
            .order_by(AssessmentAttempt.started_at.asc())
            .limit(limit)
            .with_for_update(skip_locked=True, of=AssessmentAttempt)
        )
        finalized = 0
        for attempt, paper in result.all():
            due_at = AssessmentService._due_at_of(paper)
            if due_at is None or due_at > now:
                continue
            # 复用收尾逻辑：算总分，并按是否还有未批改的主观题定状态
            await AssessmentService._finalize_attempt(db, attempt)
            finalized += 1
        return finalized

    BEHAVIOR_FLAG_TYPES = {
        "fullscreen_exit",
        "fullscreen_denied",
        "blocked_paste",
        "blocked_copy",
        "blocked_cut",
        "blocked_shortcut",
        "blocked_insert",
        "blocked_drop",
        "blocked_contextmenu",
        "blocked_selection",
        "blocked_drag",
        "blocked_exec",
        "clipboard_read",
        "devtools_open",
        "focus_loss",
        "visibility_hidden",
    }

    @staticmethod
    async def list_paper_attempts(
        db: AsyncSession, paper_id: UUID, teacher_id: UUID
    ) -> List[Dict[str, Any]]:
        await AssessmentService.get_paper(db, paper_id, teacher_id)

        result = await db.execute(
            select(AssessmentAttempt, User.nickname, User.username)
            .join(User, User.id == AssessmentAttempt.student_id)
            .where(AssessmentAttempt.paper_id == paper_id)
            .order_by(AssessmentAttempt.created_at.desc())
        )
        rows = result.all()
        attempt_ids = [a.id for a, _, _ in rows]

        stats: Dict[UUID, Dict[str, int]] = {
            aid: {"total": 0, "flagged": 0, "pending": 0} for aid in attempt_ids
        }
        if attempt_ids:
            event_rows = await db.execute(
                select(
                    BehaviorEvent.attempt_id,
                    BehaviorEvent.event_type,
                    func.count(BehaviorEvent.id),
                )
                .where(BehaviorEvent.attempt_id.in_(attempt_ids))
                .group_by(BehaviorEvent.attempt_id, BehaviorEvent.event_type)
            )
            for aid, event_type, cnt in event_rows.all():
                if aid not in stats:
                    continue
                stats[aid]["total"] += cnt
                if event_type in AssessmentService.BEHAVIOR_FLAG_TYPES:
                    stats[aid]["flagged"] += cnt

        if attempt_ids:
            pending_rows = await db.execute(
                select(AssessmentAnswer.attempt_id, func.count(AssessmentAnswer.id))
                .join(AssessmentQuestion, AssessmentQuestion.id == AssessmentAnswer.question_id)
                .where(
                    AssessmentAnswer.attempt_id.in_(attempt_ids),
                    AssessmentAnswer.graded.is_(False),
                    AssessmentQuestion.paper_id == paper_id,
                )
                .group_by(AssessmentAnswer.attempt_id)
            )
            for aid, cnt in pending_rows.all():
                if aid in stats:
                    stats[aid]["pending"] = cnt

        out: List[Dict[str, Any]] = []
        for attempt, nickname, username in rows:
            s = stats.get(attempt.id, {"total": 0, "flagged": 0, "pending": 0})
            out.append(
                {
                    "id": attempt.id,
                    "student_id": attempt.student_id,
                    "student_name": nickname or username,
                    "username": username,
                    "status": attempt.status,
                    "started_at": attempt.started_at,
                    "submitted_at": attempt.submitted_at,
                    "duration_seconds": attempt.duration_seconds,
                    "score": attempt.score,
                    "suspicious": bool(attempt.suspicious or s["flagged"] > 0),
                    "event_count": s["total"],
                    "flagged_count": s["flagged"],
                    # 仅已交卷的作答才有「待批改」语义：作答中的学生随时可能继续改答案，
                    # 显示批改入口只会让教师点进去撞「尚未交卷」的报错。
                    "pending_grade_count": s["pending"] if attempt.status != "in_progress" else 0,
                }
            )
        return out

    @staticmethod
    async def list_attempt_behavior(
        db: AsyncSession, attempt_id: UUID, teacher_id: UUID
    ) -> List[Dict[str, Any]]:
        result = await db.execute(
            select(AssessmentAttempt).where(AssessmentAttempt.id == attempt_id)
        )
        attempt = result.scalars().first()
        if not attempt:
            raise NotFoundError("作答记录不存在")

        paper_result = await db.execute(
            select(AssessmentPaper).where(AssessmentPaper.id == attempt.paper_id)
        )
        paper = paper_result.scalars().first()
        if not paper or paper.creator_id != teacher_id:
            raise NotFoundError("试卷不存在")

        event_result = await db.execute(
            select(BehaviorEvent)
            .where(BehaviorEvent.attempt_id == attempt_id)
            .order_by(BehaviorEvent.created_at.asc())
        )
        events = event_result.scalars().all()
        return [
            {
                "id": e.id,
                "event_type": e.event_type,
                "payload": e.payload,
                "occurred_at": e.occurred_at,
            }
            for e in events
        ]

    @staticmethod
    def _to_float_safe(value: Any, default: float) -> float:
        try:
            if value is None or value == "":
                return default
            return float(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _to_uuid_list(items: Any) -> List[UUID]:
        # publish_target 是自由 dict，内层值不受 schema 约束。标量（如 ids: 1）
        # 直接迭代会抛 TypeError 冒到全局兜底变成 500，这里统一收敛为「无有效值」。
        if isinstance(items, (str, UUID)):
            items = [items]
        elif not isinstance(items, (list, tuple, set)):
            return []
        out: List[UUID] = []
        for it in items:
            try:
                out.append(UUID(str(it)))
            except (ValueError, TypeError):
                continue
        return out

    @staticmethod
    def _norm(value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, (dict, list)):
            return json.dumps(value, ensure_ascii=False, sort_keys=True)
        return str(value).strip().lower()

    @staticmethod
    def _to_list(value: Any) -> List[str]:
        if value is None:
            return []
        if isinstance(value, list):
            return [str(v).strip().lower() for v in value]
        if isinstance(value, str):
            parts = [
                p.strip().lower()
                for p in value.replace("、", ",").replace(";", ",").replace("；", ",").split(",")
            ]
            return [p for p in parts if p]
        return [str(value).strip().lower()]

    @staticmethod
    def _judge(question: AssessmentQuestion, answer: Any) -> Optional[bool]:
        qtype = question.question_type
        if qtype not in ("single", "multiple", "judge", "fill"):
            return None
        if qtype == "multiple":
            a_set = set(AssessmentService._to_list(answer))
            r_set = set(AssessmentService._to_list(question.answer))
            return bool(a_set) and a_set == r_set
        if qtype == "judge":
            truthy = {"对", "true", "正确", "t", "是", "yes", "1", "√"}
            falsy = {"错", "false", "错误", "f", "否", "no", "0", "×"}

            def to_bool(value: Any) -> Optional[bool]:
                n = AssessmentService._norm(value)
                if n in truthy:
                    return True
                if n in falsy:
                    return False
                return None

            a_bool = to_bool(answer)
            r_bool = to_bool(question.answer)
            return a_bool is not None and a_bool == r_bool
        return AssessmentService._norm(answer) == AssessmentService._norm(question.answer)

    @staticmethod
    async def _own_student_ids(db: AsyncSession, teacher_id: UUID, student_ids: List[str]) -> set:
        """返回其中确实属于该教师所带班级的学生 id 集合。"""
        ids = AssessmentService._to_uuid_list(student_ids)
        if not ids:
            return set()
        result = await db.execute(
            select(ClassMember.user_id)
            .join(ClassGroup, ClassGroup.id == ClassMember.class_id)
            .where(
                ClassGroup.teacher_id == teacher_id,
                ClassMember.user_id.in_(ids),
                ClassMember.status == "active",
                ClassMember.deleted_at.is_(None),
            )
        )
        return {str(uid) for uid in result.scalars().all()}

    @staticmethod
    async def _resolve_student_identifiers(
        db: AsyncSession, values: List[Any], teacher_id: Optional[UUID] = None
    ) -> List[str]:
        if isinstance(values, str):
            values = [values]
        elif values and not isinstance(values, (list, tuple, set)):
            # 同上：whitelist / student_ids 传成标量时不能让迭代炸成 500
            return []
        if not values:
            return []
        resolved: List[str] = []
        seen = set()
        for v in values:
            raw = str(v).strip()
            if not raw:
                continue
            match = None
            try:
                uid = UUID(raw)
                result = await db.execute(
                    select(User).where(User.id == uid, User.deleted_at.is_(None))
                )
                match = result.scalars().first()
            except (ValueError, TypeError):
                result = await db.execute(
                    select(User)
                    .outerjoin(StudentProfile, StudentProfile.user_id == User.id)
                    .where(
                        or_(
                            func.lower(User.username) == raw.lower(),
                            StudentProfile.student_id == raw,
                        ),
                        User.deleted_at.is_(None),
                    )
                )
                match = result.scalars().first()
            if match and str(match.id) not in seen:
                seen.add(str(match.id))
                resolved.append(str(match.id))

        # 限定为自己班级的学生，避免教师把试卷指派给非本班学生
        if teacher_id is not None and resolved:
            own = await AssessmentService._own_student_ids(db, teacher_id, resolved)
            resolved = [sid for sid in resolved if sid in own]
        return resolved

    @staticmethod
    async def _is_targeted(db: AsyncSession, student_id: UUID, target: Dict[str, Any]) -> bool:
        target = target or {}
        ids = target.get("ids") or []
        whitelist = target.get("whitelist") or []
        blacklist = target.get("blacklist") or []
        student_str = str(student_id)

        if student_str in [str(i) for i in blacklist]:
            return False

        ttype = str(target.get("type") or "").strip()
        if ttype == "student":
            return student_str in [str(i) for i in ids] or student_str in [str(i) for i in whitelist]

        if student_str in [str(i) for i in whitelist]:
            return True

        class_ids = AssessmentService._to_uuid_list(ids)
        if not class_ids:
            return False

        subset_ids = target.get("student_ids") or []
        subset_str = [str(i) for i in subset_ids]
        if subset_str:
            return student_str in subset_str

        result = await db.execute(
            select(ClassMember).where(
                ClassMember.user_id == student_id,
                ClassMember.class_id.in_(class_ids),
                ClassMember.status == "active",
                ClassMember.deleted_at.is_(None),
            )
        )
        return result.scalars().first() is not None

    @staticmethod
    def _due_at_of(paper: AssessmentPaper) -> Optional[datetime]:
        raw = (paper.publish_target or {}).get("due_at")
        if not raw:
            return None
        try:
            parsed = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        except (ValueError, TypeError):
            return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed

    @staticmethod
    def _ensure_not_expired(paper: AssessmentPaper) -> None:
        due_at = AssessmentService._due_at_of(paper)
        if due_at is not None and datetime.now(timezone.utc) > due_at:
            raise ValidationError("已超过截止时间，无法继续作答")

    @staticmethod
    async def _get_latest_attempt(
        db: AsyncSession, paper_id: UUID, student_id: UUID
    ) -> Optional[AssessmentAttempt]:
        result = await db.execute(
            select(AssessmentAttempt)
            .where(AssessmentAttempt.paper_id == paper_id, AssessmentAttempt.student_id == student_id)
            .order_by(AssessmentAttempt.created_at.desc())
        )
        return result.scalars().first()

    @staticmethod
    async def _get_published_paper_for_student(
        db: AsyncSession, paper_id: UUID, student_id: UUID
    ) -> AssessmentPaper:
        paper = (
            await db.execute(
                select(AssessmentPaper).where(
                    AssessmentPaper.id == paper_id,
                    AssessmentPaper.deleted_at.is_(None),
                )
            )
        ).scalars().first()
        if not paper or paper.parse_status != "published":
            raise NotFoundError("试卷不存在或未发布")
        if not await AssessmentService._is_targeted(db, student_id, paper.publish_target or {}):
            raise PermissionDenied("你不在该试卷的发布范围内")
        return paper

    @staticmethod
    async def list_student_papers(db: AsyncSession, student_id: UUID) -> List[Dict[str, Any]]:
        result = await db.execute(
            select(AssessmentPaper)
            .where(AssessmentPaper.parse_status == "published", AssessmentPaper.deleted_at.is_(None))
            .order_by(AssessmentPaper.published_at.desc())
        )
        out: List[Dict[str, Any]] = []
        for paper in result.scalars().all():
            target = paper.publish_target or {}
            if not await AssessmentService._is_targeted(db, student_id, target):
                continue

            due_at = None
            due_raw = target.get("due_at")
            if due_raw:
                try:
                    due_at = datetime.fromisoformat(str(due_raw).replace("Z", "+00:00"))
                except (ValueError, TypeError):
                    due_at = None

            attempt = await AssessmentService._get_latest_attempt(db, paper.id, student_id)
            out.append(
                {
                    "id": paper.id,
                    "title": paper.title,
                    "description": paper.description,
                    "question_count": paper.question_count,
                    "total_score": paper.total_score,
                    "published_at": paper.published_at,
                    "due_at": due_at,
                    "attempt_id": attempt.id if attempt else None,
                    "attempt_status": attempt.status if attempt else None,
                    "attempt_score": attempt.score if attempt else None,
                }
            )
        return out

    @staticmethod
    async def get_student_questions(
        db: AsyncSession, paper_id: UUID, student_id: UUID
    ) -> List[AssessmentQuestion]:
        await AssessmentService._get_published_paper_for_student(db, paper_id, student_id)
        result = await db.execute(
            select(AssessmentQuestion)
            .where(AssessmentQuestion.paper_id == paper_id)
            .order_by(AssessmentQuestion.order_index.asc())
        )
        return list(result.scalars().all())

    @staticmethod
    async def get_or_create_attempt(
        db: AsyncSession, paper_id: UUID, student_id: UUID
    ) -> AssessmentAttempt:
        paper = await AssessmentService._get_published_paper_for_student(db, paper_id, student_id)
        attempt = await AssessmentService._get_latest_attempt(db, paper_id, student_id)
        if attempt:
            return await AssessmentService._enforce_violation_limit(db, attempt)

        AssessmentService._ensure_not_expired(paper)
        attempt = AssessmentAttempt(
            paper_id=paper_id,
            student_id=student_id,
            status="in_progress",
            started_at=datetime.now(timezone.utc),
        )
        db.add(attempt)
        try:
            await db.commit()
        except IntegrityError:
            # 并发下另一个请求已建好作答，(paper_id, student_id) 唯一约束兜底
            await db.rollback()
            existing = await AssessmentService._get_latest_attempt(db, paper_id, student_id)
            if existing:
                return existing
            raise
        await db.refresh(attempt)
        return attempt

    @staticmethod
    async def _upsert_answers(
        db: AsyncSession, attempt: AssessmentAttempt, answers: List[Dict[str, Any]]
    ) -> None:
        question_ids = AssessmentService._to_uuid_list([a.get("question_id") for a in answers])
        if question_ids:
            q_result = await db.execute(
                select(AssessmentQuestion).where(
                    AssessmentQuestion.id.in_(question_ids),
                    AssessmentQuestion.paper_id == attempt.paper_id,
                )
            )
        else:
            q_result = None

        qmap = {q.id: q for q in (q_result.scalars().all() if q_result else [])}

        existing_result = await db.execute(
            select(AssessmentAnswer).where(AssessmentAnswer.attempt_id == attempt.id)
        )
        existing = {a.question_id: a for a in existing_result.scalars().all()}

        for a in answers:
            try:
                qid = UUID(str(a.get("question_id")))
            except (ValueError, TypeError):
                continue
            q = qmap.get(qid)
            if not q:
                continue
            correct = AssessmentService._judge(q, a.get("answer"))
            graded = q.question_type in ("single", "multiple", "judge", "fill")
            row = existing.get(qid)
            if row:
                row.answer = a.get("answer")
                row.is_correct = correct
                row.score = q.score if correct else 0.0
                row.graded = graded
            else:
                db.add(
                    AssessmentAnswer(
                        attempt_id=attempt.id,
                        question_id=qid,
                        answer=a.get("answer"),
                        is_correct=correct,
                        score=q.score if correct else 0.0,
                        graded=graded,
                    )
                )

    @staticmethod
    async def _load_student_attempt(
        db: AsyncSession, attempt_id: UUID, student_id: UUID, enforce_due: bool = True
    ) -> AssessmentAttempt:
        """按 attempt_id + student_id 取作答。

        enforce_due 仅用于「继续答题」类操作；交卷是收尾动作，过期后仍必须放行，
        否则到点自动交卷会被服务端拒绝，学生反而交不了卷。
        """
        result = await db.execute(
            select(AssessmentAttempt)
            .where(
                AssessmentAttempt.id == attempt_id, AssessmentAttempt.student_id == student_id
            )
            .with_for_update()
        )
        attempt = result.scalars().first()
        if not attempt:
            raise NotFoundError("作答记录不存在")

        paper = (
            await db.execute(
                select(AssessmentPaper).where(AssessmentPaper.id == attempt.paper_id)
            )
        ).scalars().first()
        if not paper:
            raise NotFoundError("试卷不存在")
        if enforce_due:
            AssessmentService._ensure_not_expired(paper)
        return attempt

    @staticmethod
    async def save_answers(
        db: AsyncSession, attempt_id: UUID, student_id: UUID, answers: List[Dict[str, Any]]
    ) -> Optional[AssessmentAttempt]:
        """保存草稿。

        返回非 None 表示本次保存触发了服务端强制交卷（违规超限），
        调用方需要把该 attempt 回给学生，让前端同步切到已交卷态。
        """
        attempt = await AssessmentService._load_student_attempt(db, attempt_id, student_id)
        if attempt.status != "in_progress":
            raise ValidationError("已交卷，无法继续保存")

        # 先把答案落库再判定是否强制交卷：反过来的话，学生最后一次输入会丢。
        await AssessmentService._upsert_answers(db, attempt, answers)
        await db.flush()

        if not await AssessmentService._violation_limit_reached(db, attempt):
            await db.commit()
            return None

        logger.info("Attempt %s exceeded fullscreen-exit limit on save; force submitting", attempt.id)
        return await AssessmentService._finalize_attempt(db, attempt)

    @staticmethod
    async def _finalize_attempt(db: AsyncSession, attempt: AssessmentAttempt) -> AssessmentAttempt:
        """按已落库的答案结算一次作答：算总分并定状态。"""
        # 会话是 autoflush=False，刚 db.add() 的答案行对下面的 SELECT 不可见，
        # 必须先 flush，否则新作答不计入总分、pending 也统计不到（主观题会被锁成 0 分）。
        await db.flush()
        answered = await db.execute(
            select(AssessmentAnswer).where(
                AssessmentAnswer.attempt_id == attempt.id,
                AssessmentAnswer.question_id.in_(
                    select(AssessmentQuestion.id).where(AssessmentQuestion.paper_id == attempt.paper_id)
                ),
            )
        )
        attempt.score = sum(a.score or 0.0 for a in answered.scalars().all())

        pending = await db.execute(
            select(func.count(AssessmentAnswer.id)).where(
                AssessmentAnswer.attempt_id == attempt.id,
                AssessmentAnswer.graded.is_(False),
                AssessmentAnswer.question_id.in_(
                    select(AssessmentQuestion.id).where(AssessmentQuestion.paper_id == attempt.paper_id)
                ),
            )
        )
        # 存在未批改的主观题时不直接定分，等教师批改后再落最终分
        attempt.status = "pending_review" if (pending.scalar() or 0) > 0 else "submitted"
        attempt.submitted_at = datetime.now(timezone.utc)
        if attempt.started_at:
            attempt.duration_seconds = max(
                0, int((attempt.submitted_at - attempt.started_at).total_seconds())
            )
        await db.commit()
        await db.refresh(attempt)
        return attempt

    @staticmethod
    async def _violation_limit_reached(db: AsyncSession, attempt: AssessmentAttempt) -> bool:
        """退出全屏次数是否已达上限。

        前端计数只存在内存 ref 里，刷新即清零，必须由服务端按 behavior_events 独立判定。
        """
        if attempt.status != "in_progress":
            return False
        count = await db.execute(
            select(func.count(BehaviorEvent.id)).where(
                BehaviorEvent.attempt_id == attempt.id,
                BehaviorEvent.event_type == "fullscreen_exit",
            )
        )
        return (count.scalar() or 0) >= AssessmentService.FULLSCREEN_EXIT_LIMIT

    @staticmethod
    async def _enforce_violation_limit(
        db: AsyncSession, attempt: AssessmentAttempt
    ) -> AssessmentAttempt:
        """违规超限时由服务端强制交卷（进入作答时兜底）。"""
        if await AssessmentService._violation_limit_reached(db, attempt):
            logger.info("Attempt %s exceeded fullscreen-exit limit; force submitting", attempt.id)
            return await AssessmentService._finalize_attempt(db, attempt)
        return attempt

    @staticmethod
    async def submit_attempt(
        db: AsyncSession, attempt_id: UUID, student_id: UUID, answers: List[Dict[str, Any]]
    ) -> AssessmentAttempt:
        attempt = await AssessmentService._load_student_attempt(
            db, attempt_id, student_id, enforce_due=False
        )
        if attempt.status != "in_progress":
            raise ValidationError("已交卷，不能重复提交")

        # 过期后仍要放行交卷（否则到点自动交卷会被服务端拒绝），但不能再接收新答案：
        # 否则学生等到截止后照常作答、再调这个接口，答案就会被写库并计分，
        # due_at 对答案内容等于没有约束力。
        paper = (
            await db.execute(
                select(AssessmentPaper).where(AssessmentPaper.id == attempt.paper_id)
            )
        ).scalars().first()
        due_at = AssessmentService._due_at_of(paper) if paper else None
        if due_at is not None and datetime.now(timezone.utc) > due_at:
            logger.info("Attempt %s submitted after due_at; ignoring client answers", attempt.id)
            return await AssessmentService._finalize_attempt(db, attempt)

        await AssessmentService._upsert_answers(db, attempt, answers)
        return await AssessmentService._finalize_attempt(db, attempt)

    @staticmethod
    async def get_student_answers(
        db: AsyncSession, paper_id: UUID, student_id: UUID
    ) -> Dict[str, Any]:
        """学生回读自己已保存的作答。

        过期后仍允许读取（只是不能再改），否则学生刷新页面就会看到空白卷面，
        而已保存的答案仍在库里参与判分。
        """
        await AssessmentService._get_published_paper_for_student(db, paper_id, student_id)
        attempt = await AssessmentService._get_latest_attempt(db, paper_id, student_id)
        if not attempt:
            return {"attempt_id": None, "status": None, "answers": []}
        rows = await db.execute(
            select(AssessmentAnswer).where(
                AssessmentAnswer.attempt_id == attempt.id,
                AssessmentAnswer.question_id.in_(
                    select(AssessmentQuestion.id).where(AssessmentQuestion.paper_id == paper_id)
                ),
            )
        )
        return {
            "attempt_id": attempt.id,
            "status": attempt.status,
            "answers": [
                {"question_id": a.question_id, "answer": a.answer}
                for a in rows.scalars().all()
            ],
        }

    @staticmethod
    async def grade_attempt(
        db: AsyncSession,
        attempt_id: UUID,
        teacher_id: UUID,
        grades: List[Dict[str, Any]],
    ) -> AssessmentAttempt:
        """教师批改主观题：逐题给分，全部批完后重算总分并置为已交卷。"""
        attempt = (
            await db.execute(
                select(AssessmentAttempt).where(AssessmentAttempt.id == attempt_id)
            )
        ).scalars().first()
        if not attempt:
            raise NotFoundError("作答记录不存在")
        # 先做所有权校验再判状态：反过来的话，非本人试卷的 in_progress 作答
        # 会返回 400「尚未交卷」而非 404，成了可枚举的探测预言机。
        await AssessmentService.get_paper(db, attempt.paper_id, teacher_id)
        # 未交卷的作答不能批：批完会把状态改成已交卷，学生会被锁死在考试中
        if attempt.status == "in_progress":
            raise ValidationError("该作答尚未交卷，无法批改")

        rows = (
            await db.execute(
                select(AssessmentAnswer, AssessmentQuestion)
                .join(AssessmentQuestion, AssessmentQuestion.id == AssessmentAnswer.question_id)
                .where(
                    AssessmentAnswer.attempt_id == attempt_id,
                    AssessmentQuestion.paper_id == attempt.paper_id,
                )
            )
        ).all()
        by_question = {q.id: (a, q) for a, q in rows}

        for g in grades:
            try:
                qid = UUID(str(g.get("question_id")))
            except (ValueError, TypeError):
                continue
            pair = by_question.get(qid)
            if not pair:
                continue
            answer_row, question = pair
            # fill 由 _judge 自动判分（见 _upsert_answers），此处只处理主观题
            if question.question_type not in ("short", "essay"):
                continue
            raw = AssessmentService._to_float_safe(g.get("score"), 0.0)
            answer_row.score = max(0.0, min(float(question.score or 0.0), raw))
            answer_row.graded = True
            answer_row.is_correct = None

        # 每次都重算总分并定状态：保留「只存分数不结算」的分支会让
        # attempt.score 与 answer.score 静默不一致，而没有任何调用方需要它。
        # autoflush=False：上面刚改的 graded/score 只在内存里，
        # 不 flush 的话下面的统计读不到，状态会永远停在 pending_review。
        await db.flush()
        in_paper = select(AssessmentQuestion.id).where(
            AssessmentQuestion.paper_id == attempt.paper_id
        )
        answered = await db.execute(
            select(AssessmentAnswer).where(
                AssessmentAnswer.attempt_id == attempt_id,
                AssessmentAnswer.question_id.in_(in_paper),
            )
        )
        attempt.score = sum(a.score or 0.0 for a in answered.scalars().all())
        # 仍有未给分的主观题时必须停在待批改，否则剩余题目会被永久锁成 0 分。
        still_pending = await db.execute(
            select(func.count(AssessmentAnswer.id)).where(
                AssessmentAnswer.attempt_id == attempt_id,
                AssessmentAnswer.graded.is_(False),
                AssessmentAnswer.question_id.in_(in_paper),
            )
        )
        attempt.status = "pending_review" if (still_pending.scalar() or 0) > 0 else "submitted"

        await db.commit()
        await db.refresh(attempt)
        return attempt

    @staticmethod
    async def list_attempt_answers(
        db: AsyncSession, attempt_id: UUID, teacher_id: UUID
    ) -> List[Dict[str, Any]]:
        """教师查看某次作答的逐题答案，用于批改。"""
        attempt = (
            await db.execute(
                select(AssessmentAttempt).where(AssessmentAttempt.id == attempt_id)
            )
        ).scalars().first()
        if not attempt:
            raise NotFoundError("作答记录不存在")
        await AssessmentService.get_paper(db, attempt.paper_id, teacher_id)

        rows = (
            await db.execute(
                select(AssessmentAnswer, AssessmentQuestion)
                .join(AssessmentQuestion, AssessmentQuestion.id == AssessmentAnswer.question_id)
                .where(
                    AssessmentAnswer.attempt_id == attempt_id,
                    AssessmentQuestion.paper_id == attempt.paper_id,
                )
                .order_by(AssessmentQuestion.order_index.asc())
            )
        ).all()
        return [
            {
                "question_id": q.id,
                "order_index": q.order_index,
                "question_type": q.question_type,
                "stem": q.stem,
                "options": q.options,
                "reference_answer": q.answer,
                "max_score": q.score,
                "answer": a.answer,
                "score": a.score,
                "graded": a.graded,
                "is_correct": a.is_correct,
            }
            for a, q in rows
        ]

    @staticmethod
    async def batch_save_behavior(
        db: AsyncSession,
        student_id: UUID,
        session_id: str,
        events: List[Dict[str, Any]],
        attempt_id: Optional[UUID] = None,
    ) -> int:
        # 只允许把行为事件挂到自己的作答上，否则可伪造他人 attempt_id 栽赃违规记录。
        if attempt_id is not None:
            owned = await db.execute(
                select(AssessmentAttempt.id).where(
                    AssessmentAttempt.id == attempt_id,
                    AssessmentAttempt.student_id == student_id,
                )
            )
            if owned.scalars().first() is None:
                raise PermissionDenied("作答记录不存在或不属于当前用户")

        now = datetime.now(timezone.utc)
        for e in events:
            db.add(
                BehaviorEvent(
                    user_id=student_id,
                    session_id=session_id,
                    attempt_id=attempt_id,
                    event_type=str(e.get("event_type") or "custom"),
                    payload=e.get("payload"),
                    occurred_at=e.get("occurred_at") or now,
                )
            )
        await db.commit()
        return len(events)

    @staticmethod
    def _attach_stem_images(stem: str, doc_images: List[dict]) -> Optional[List[dict]]:
        if not stem or not doc_images:
            return None
        indices = {int(n) for n in IMG_RE.findall(stem)}
        matched = [
            {"index": img["index"], "url": img["url"]}
            for img in doc_images
            if img["index"] in indices
        ]
        return matched or None

    @staticmethod
    async def run_parse(db: AsyncSession, paper_id: UUID) -> None:
        paper = (
            await db.execute(
                select(AssessmentPaper).where(AssessmentPaper.id == paper_id)
            )
        ).scalars().first()
        if not paper:
            raise NotFoundError("试卷不存在")

        try:
            paper.parse_status = "parsing"
            paper.parse_error = None
            await db.commit()
            await AssessmentService.set_parse_progress(paper_id, {"stage": "downloading", "total": 0, "done": 0})

            file = (
                await db.execute(
                    select(FileModel).where(FileModel.id == paper.source_file_id)
                )
            ).scalars().first()
            if not file:
                raise ValidationError("源文件已不存在")

            file_bytes = await asyncio.to_thread(MinioService.download_file, file.storage_path)
            raw_text = parse_document(file_bytes, file.original_name)
            if not raw_text.strip():
                raise ValidationError("文档解析为空，无有效可提取文本")

            extracted_images = await asyncio.to_thread(extract_images, file_bytes, file.original_name)
            doc_images: List[dict] = []
            for idx, im in enumerate(extracted_images, start=1):
                ext = im.get("ext") or "png"
                object_name = f"assessment/images/{paper_id}/img_{idx}.{ext}"
                data = im.get("data") or b""
                if not data:
                    continue
                await asyncio.to_thread(
                    MinioService.upload_file,
                    object_name,
                    io.BytesIO(data),
                    len(data),
                    f"image/{ext}",
                )
                url = await asyncio.to_thread(MinioService.get_download_url, object_name, 7 * 24 * 3600)
                doc_images.append({"index": idx, "object_name": object_name, "url": url})

            progress_state = {"total": 0, "done": 0}

            async def on_progress(stage: str, value: int) -> None:
                if stage == "mechanical":
                    progress_state["total"] = value
                    progress_state["done"] = 0
                else:
                    progress_state["done"] = value
                await AssessmentService.set_parse_progress(
                    paper_id,
                    {
                        "stage": "extracting",
                        "total": progress_state["total"],
                        "done": progress_state["done"],
                    },
                )

            questions = await question_parser_module.parse_text_to_questions(raw_text, on_progress=on_progress)
            for q in questions:
                q["stem_images"] = AssessmentService._attach_stem_images(q.get("stem") or "", doc_images)

            # 解析期间教师可能已手工校对并保存，若状态已变则放弃写入，避免覆盖人工编辑
            # （同时也避免重建题目级联删除学生作答）。
            await db.refresh(paper)
            if paper.parse_status != "parsing":
                logger.info("Paper %s status changed to %s during parse; skip overwrite", paper_id, paper.parse_status)
                return

            await db.execute(delete(AssessmentQuestion).where(AssessmentQuestion.paper_id == paper_id))

            total_score = 0.0
            for q in questions:
                score = float(q.get("score") or 0.0)
                total_score += score
                db.add(
                    AssessmentQuestion(
                        paper_id=paper_id,
                        order_index=q["order_index"],
                        question_type=q["question_type"],
                        stem=q["stem"],
                        stem_images=q.get("stem_images") or None,
                        options=q.get("options") or None,
                        answer=q.get("answer"),
                        analysis=q.get("analysis"),
                        score=score,
                        difficulty=q.get("difficulty"),
                        tags=q.get("tags") or None,
                        source_chunk=q.get("source_chunk"),
                    )
                )

            paper.question_count = len(questions)
            paper.total_score = total_score
            paper.parse_status = "awaiting_review"
            paper.parse_error = None
            await db.commit()
            await AssessmentService.set_parse_progress(
                paper_id,
                {"stage": "done", "total": len(questions), "done": len(questions)},
            )
        except Exception as exc:
            paper.parse_status = "failed"
            paper.parse_error = str(exc)[:1000]
            await db.commit()
            await AssessmentService.set_parse_progress(
                paper_id,
                {"stage": "failed", "error": str(exc)[:200]},
            )
            raise