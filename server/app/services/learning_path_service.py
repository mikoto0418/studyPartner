import hashlib
import re
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from sqlalchemy import and_, delete, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import NotFoundError, PermissionDenied, ValidationError
from app.models.learning_path import (
    ClassGroup,
    ClassMember,
    LearningNodeProgress,
    LearningNodeSubmission,
    LearningPathAssignee,
    LearningPathEdge,
    LearningPathNode,
    LearningPathResource,
    LearningPathStage,
    LearningPathTask,
    LearningInsight,
)
from app.models.student_memory import DailyReview, StudentMemory
from app.models.user import User
from app.schemas.learning_path import (
    ClassCreate,
    LearningNodeReviewReq,
    LearningNodeSubmitReq,
    LearningInsightStatusUpdate,
    LearningPathCreate,
    LearningPathEdgeIn,
    LearningPathNodeIn,
    LearningPathResourceIn,
    LearningPathStageIn,
    LearningPathUpdate,
)
from app.services.access_control import AccessControlService
from app.services.notification_service import NotificationService
from app.utils.display_name import user_display_name


class LearningPathPlanner:
    """Deterministic first version of the AI planner.

    The shape is intentionally LLM-ready: a later implementation can replace
    this method with a model call while keeping the same JSON contract.
    """

    STEP_SPLIT_PATTERN = re.compile(r"(?:\s*(?:先|再|然后|接着|最后|其次|之后|，|。|；|;|\n)\s*)+")
    BV_PATTERN = re.compile(r"\b(BV[0-9A-Za-z]{10,})\b")

    @classmethod
    def build_plan(cls, goal: str, planning_text: str) -> Dict[str, Any]:
        raw_parts = [part.strip(" ，。；;") for part in cls.STEP_SPLIT_PATTERN.split(planning_text or "") if part.strip()]
        parts = cls._normalize_parts(raw_parts, goal)

        stages = cls._build_stages(parts)
        nodes: List[Dict[str, Any]] = []
        resources: List[Dict[str, Any]] = []

        for index, part in enumerate(parts):
            node_type = cls._infer_node_type(part, index, len(parts))
            node_key = f"node_{index + 1}"
            node_resource_list = cls._extract_resources(part, node_key)
            resources.extend(node_resource_list)
            nodes.append({
                "key": node_key,
                "title": cls._build_title(part, node_type, index),
                "description": part,
                "node_type": node_type,
                "order_index": index,
                "estimated_minutes": cls._estimate_minutes(node_type),
                "required": True,
                "config": {
                    "source": "rule_planner",
                    "stage_order": cls._stage_order_for_index(index, len(parts)),
                },
                "resources": node_resource_list,
            })

        edges = [
            {
                "source_key": nodes[index]["key"],
                "target_key": nodes[index + 1]["key"],
            }
            for index in range(max(0, len(nodes) - 1))
        ]

        return {
            "stages": stages,
            "nodes": nodes,
            "edges": edges,
            "resources": resources,
            "summary": f"已将「{goal}」拆解为 {len(nodes)} 个可执行节点，按理解、练习、提交复盘逐步推进。",
        }

    @classmethod
    def _normalize_parts(cls, parts: List[str], goal: str) -> List[str]:
        if len(parts) >= 3:
            normalized = parts
        else:
            topic = goal.strip() or "当前主题"
            normalized = [
                f"理解{topic}的核心概念和学习目标",
                f"观看或阅读{topic}的基础材料并记录关键问题",
                f"完成{topic}的小练习或案例验证",
                f"提交{topic}学习总结和后续问题",
            ]

        if not any(cls._infer_node_type(part, idx, len(normalized)) == "submission" for idx, part in enumerate(normalized)):
            normalized.append(f"提交{goal.strip() or '本次学习'}总结、附件或反思文档")
        return normalized[:12]

    @classmethod
    def _build_stages(cls, parts: List[str]) -> List[Dict[str, Any]]:
        if len(parts) <= 4:
            return [
                {"title": "理解与输入", "description": "建立概念框架，完成必要材料学习。", "order_index": 0},
                {"title": "练习与产出", "description": "通过练习、提交和反馈完成闭环。", "order_index": 1},
            ]
        return [
            {"title": "准备", "description": "明确目标并完成基础输入。", "order_index": 0},
            {"title": "推进", "description": "按节点完成练习、阅读、观看和阶段检查。", "order_index": 1},
            {"title": "交付", "description": "提交成果，等待教师反馈并二次完善。", "order_index": 2},
        ]

    @staticmethod
    def _stage_order_for_index(index: int, total: int) -> int:
        if total <= 4:
            return 0 if index < max(1, total // 2) else 1
        if index < max(1, total // 3):
            return 0
        if index < max(2, total - 1):
            return 1
        return 2

    @classmethod
    def _extract_resources(cls, text: str, node_key: str) -> List[Dict[str, Any]]:
        resources = []
        for match in cls.BV_PATTERN.findall(text or ""):
            resources.append({
                "resource_type": "bilibili",
                "title": f"B 站视频 {match}",
                "url": f"https://www.bilibili.com/video/{match}",
                "bv_id": match,
                "file_id": None,
                "metadata": {"node_key": node_key},
            })
        return resources

    @classmethod
    def _infer_node_type(cls, text: str, index: int, total: int) -> str:
        lower_text = text.lower()
        if cls.BV_PATTERN.search(text) or "视频" in text or "b站" in lower_text or "bilibili" in lower_text:
            return "video"
        if any(keyword in text for keyword in ["阅读", "文档", "资料", "论文", "课件"]):
            return "reading"
        if any(keyword in text for keyword in ["练习", "实验", "复现", "实现", "代码", "案例"]):
            return "practice"
        if any(keyword in text for keyword in ["提交", "总结", "报告", "作业", "附件"]) or index == total - 1:
            return "submission"
        if any(keyword in text for keyword in ["检查", "测验", "自测", "阶段"]):
            return "checkpoint"
        return "learning"

    @staticmethod
    def _build_title(text: str, node_type: str, index: int) -> str:
        compact = re.sub(r"\s+", "", text)
        compact = re.sub(r"\bBV[0-9A-Za-z]{10,}\b", "", compact).strip(" ，。；;")
        if len(compact) > 22:
            compact = compact[:22] + "..."
        if compact:
            return compact
        labels = {
            "video": "观看课程视频",
            "reading": "阅读学习材料",
            "practice": "完成实践练习",
            "submission": "提交阶段成果",
            "checkpoint": "完成阶段检查",
        }
        return labels.get(node_type, f"学习节点 {index + 1}")

    @staticmethod
    def _estimate_minutes(node_type: str) -> int:
        return {
            "video": 45,
            "reading": 50,
            "practice": 90,
            "submission": 40,
            "checkpoint": 30,
            "learning": 45,
        }.get(node_type, 45)


class LearningPathService:
    INSIGHT_VISIBLE_STATUSES = {"new", "acknowledged"}
    INSIGHT_CLOSED_STATUSES = {"resolved", "dismissed"}
    MEMORY_CATEGORY_LABELS = {
        "goal": "学习目标",
        "interest_area": "兴趣方向",
        "learning_preference": "学习偏好",
        "study_habit": "学习习惯",
        "weakness": "薄弱点",
        "strength": "优势能力",
        "challenge": "学习阻碍",
        "knowledge_gap": "知识缺口",
    }

    @staticmethod
    async def create_class(db: AsyncSession, teacher_id: UUID, class_in: ClassCreate) -> ClassGroup:
        class_group = ClassGroup(
            teacher_id=teacher_id,
            name=class_in.name,
            description=class_in.description,
            grade=class_in.grade,
            subject=class_in.subject,
            status="active",
        )
        db.add(class_group)
        await db.flush()

        now = datetime.now(timezone.utc)
        for student_id in class_in.student_ids:
            db.add(ClassMember(
                class_id=class_group.id,
                user_id=student_id,
                role="student",
                joined_at=now,
                status="active",
            ))

        await db.commit()
        await db.refresh(class_group)
        return class_group

    @staticmethod
    async def list_classes(db: AsyncSession, teacher_id: UUID) -> List[ClassGroup]:
        result = await db.execute(
            select(ClassGroup)
            .options(selectinload(ClassGroup.members).selectinload(ClassMember.user))
            .where(and_(ClassGroup.teacher_id == teacher_id, ClassGroup.deleted_at.is_(None)))
            .order_by(desc(ClassGroup.created_at))
        )
        return list(result.scalars().all())

    @staticmethod
    async def get_class(db: AsyncSession, class_id: UUID, teacher_id: Optional[UUID] = None) -> ClassGroup:
        stmt = (
            select(ClassGroup)
            .options(selectinload(ClassGroup.members).selectinload(ClassMember.user))
            .where(and_(ClassGroup.id == class_id, ClassGroup.deleted_at.is_(None)))
        )
        if teacher_id:
            stmt = stmt.where(ClassGroup.teacher_id == teacher_id)
        result = await db.execute(stmt)
        class_group = result.scalars().first()
        if not class_group:
            raise NotFoundError("班级不存在")
        return class_group

    @staticmethod
    async def generate_plan(req_goal: str, planning_text: str) -> Dict[str, Any]:
        return LearningPathPlanner.build_plan(req_goal, planning_text)

    @staticmethod
    async def create_path(db: AsyncSession, creator_id: UUID, path_in: LearningPathCreate) -> LearningPathTask:
        plan = LearningPathPlanner.build_plan(path_in.goal, path_in.planning_text or path_in.goal)
        stage_inputs = path_in.stages or [LearningPathStageIn(**stage) for stage in plan["stages"]]
        node_inputs = path_in.nodes or [LearningPathNodeIn(**node) for node in plan["nodes"]]
        edge_inputs = path_in.edges or [LearningPathEdgeIn(**edge) for edge in plan["edges"]]
        assignee_ids = await LearningPathService._resolve_assignees(db, path_in.class_id, path_in.assignee_ids)

        now = datetime.now(timezone.utc)
        task = LearningPathTask(
            creator_id=creator_id,
            class_id=path_in.class_id,
            title=path_in.title,
            goal=path_in.goal,
            planning_text=path_in.planning_text,
            description=path_in.description,
            status="published" if path_in.publish else "draft",
            due_date=path_in.due_date,
            published_at=now if path_in.publish else None,
            ai_plan=plan,
        )
        db.add(task)
        await db.flush()

        await LearningPathService._replace_path_graph(db, task, stage_inputs, node_inputs, edge_inputs)
        if assignee_ids:
            await LearningPathService._assign_students(db, task, assignee_ids)

        await db.commit()
        await db.refresh(task)
        for student_id in assignee_ids:
            await NotificationService.create_notification(
                db,
                user_id=student_id,
                title="新的学习路径任务",
                content=f"老师发布了学习路径「{task.title}」。",
                notification_type="learning_path",
                link_url="/student/learning-paths",
            )
        return task

    @staticmethod
    async def update_path(db: AsyncSession, task_id: UUID, teacher_id: UUID, path_in: LearningPathUpdate) -> LearningPathTask:
        task = await LearningPathService.get_teacher_task(db, task_id, teacher_id)

        for field in ["title", "goal", "planning_text", "description", "status", "due_date"]:
            value = getattr(path_in, field)
            if value is not None:
                setattr(task, field, value)

        if path_in.status == "published" and task.published_at is None:
            task.published_at = datetime.now(timezone.utc)

        if path_in.nodes is not None:
            stages = path_in.stages or [
                LearningPathStageIn(title="学习路径", description="教师微调后的路径结构。", order_index=0)
            ]
            edges = path_in.edges or [
                LearningPathEdgeIn(source_key=path_in.nodes[index].key or f"node_{index + 1}", target_key=path_in.nodes[index + 1].key or f"node_{index + 2}")
                for index in range(max(0, len(path_in.nodes) - 1))
            ]
            await LearningPathService._replace_path_graph(db, task, stages, path_in.nodes, edges)

        db.add(task)
        await db.commit()
        await db.refresh(task)
        return task

    @staticmethod
    async def list_teacher_paths(db: AsyncSession, teacher_id: UUID) -> List[Dict[str, Any]]:
        tasks_result = await db.execute(
            select(LearningPathTask)
            .where(and_(LearningPathTask.creator_id == teacher_id, LearningPathTask.deleted_at.is_(None)))
            .order_by(desc(LearningPathTask.created_at))
        )
        tasks = list(tasks_result.scalars().all())
        return [await LearningPathService._task_summary(db, task) for task in tasks]

    @staticmethod
    async def list_student_paths(db: AsyncSession, student_id: UUID) -> List[Dict[str, Any]]:
        result = await db.execute(
            select(LearningPathTask, LearningPathAssignee)
            .join(LearningPathAssignee, LearningPathAssignee.task_id == LearningPathTask.id)
            .where(and_(LearningPathAssignee.user_id == student_id, LearningPathTask.deleted_at.is_(None)))
            .order_by(desc(LearningPathTask.created_at))
        )
        rows = result.all()
        output = []
        for task, assignee in rows:
            summary = await LearningPathService._task_summary(db, task)
            summary["status"] = assignee.status
            summary["avg_progress"] = round(float(assignee.progress_percent or 0), 1)
            output.append(summary)
        return output

    @staticmethod
    async def get_teacher_task(db: AsyncSession, task_id: UUID, teacher_id: UUID) -> LearningPathTask:
        result = await db.execute(
            select(LearningPathTask).where(
                and_(
                    LearningPathTask.id == task_id,
                    LearningPathTask.creator_id == teacher_id,
                    LearningPathTask.deleted_at.is_(None),
                )
            )
        )
        task = result.scalars().first()
        if not task:
            raise NotFoundError("学习路径任务不存在")
        return task

    @staticmethod
    async def get_student_task(db: AsyncSession, task_id: UUID, student_id: UUID) -> LearningPathTask:
        result = await db.execute(
            select(LearningPathTask)
            .join(LearningPathAssignee, LearningPathAssignee.task_id == LearningPathTask.id)
            .where(
                and_(
                    LearningPathTask.id == task_id,
                    LearningPathAssignee.user_id == student_id,
                    LearningPathTask.deleted_at.is_(None),
                )
            )
        )
        task = result.scalars().first()
        if not task:
            raise NotFoundError("学习路径任务不存在或未分配给你")
        return task

    @staticmethod
    async def get_path_detail(db: AsyncSession, task_id: UUID, user: User, student_view: bool = False) -> Dict[str, Any]:
        role_codes = user.role_codes
        if student_view or "student" in role_codes:
            task = await LearningPathService.get_student_task(db, task_id, user.id)
            progress_user_id = user.id
        else:
            task = await LearningPathService.get_teacher_task(db, task_id, user.id)
            progress_user_id = None

        stages, nodes, edges, resources = await LearningPathService._load_graph(db, task.id)
        progress_map = await LearningPathService._load_progress_map(db, task.id, progress_user_id)
        resource_map: Dict[UUID, List[LearningPathResource]] = {}
        for resource in resources:
            if resource.node_id:
                resource_map.setdefault(resource.node_id, []).append(resource)

        node_out = []
        for node in nodes:
            item = {
                "id": node.id,
                "task_id": node.task_id,
                "stage_id": node.stage_id,
                "key": node.key,
                "title": node.title,
                "description": node.description,
                "node_type": node.node_type,
                "order_index": node.order_index,
                "estimated_minutes": node.estimated_minutes,
                "required": node.required,
                "config": node.config,
                "resources": [LearningPathService._resource_to_dict(res) for res in resource_map.get(node.id, [])],
                "progress": progress_map.get(node.id),
            }
            node_out.append(item)

        return {
            "task": await LearningPathService._task_summary(db, task),
            "stages": stages,
            "nodes": node_out,
            "edges": edges,
            "assignees": await LearningPathService._list_assignees(db, task.id),
            "submissions": await LearningPathService._list_submissions(db, task.id),
        }

    @staticmethod
    async def submit_node(
        db: AsyncSession,
        task_id: UUID,
        node_id: UUID,
        student_id: UUID,
        submission_in: LearningNodeSubmitReq,
    ) -> LearningNodeSubmission:
        task = await LearningPathService.get_student_task(db, task_id, student_id)
        progress = await LearningPathService._get_or_create_progress(db, task_id, node_id, student_id)
        if progress.status == "locked":
            raise ValidationError("当前节点尚未解锁，请先完成前置步骤")

        now = datetime.now(timezone.utc)
        submission = LearningNodeSubmission(
            task_id=task_id,
            node_id=node_id,
            user_id=student_id,
            content=submission_in.content,
            attachment_ids=[str(item) for item in submission_in.attachment_ids],
            review_status="pending",
        )
        db.add(submission)

        progress.status = "completed" if submission_in.mark_complete else "submitted"
        progress.submitted_at = now
        if submission_in.mark_complete:
            progress.completed_at = now
        db.add(progress)

        await LearningPathService._unlock_next_nodes(db, task_id, student_id, node_id)
        await LearningPathService._recalculate_assignee_progress(db, task_id, student_id)

        await db.commit()
        await db.refresh(submission)
        await NotificationService.create_notification(
            db,
            user_id=task.creator_id,
            title="学习路径节点已提交",
            content=f"学习路径「{task.title}」收到新的节点提交。",
            notification_type="learning_path",
            link_url="/teacher/learning-paths",
        )
        return submission

    @staticmethod
    async def review_submission(
        db: AsyncSession,
        submission_id: UUID,
        teacher_id: UUID,
        review_in: LearningNodeReviewReq,
    ) -> LearningNodeSubmission:
        result = await db.execute(
            select(LearningNodeSubmission)
            .options(selectinload(LearningNodeSubmission.task))
            .where(LearningNodeSubmission.id == submission_id)
        )
        submission = result.scalars().first()
        if not submission:
            raise NotFoundError("提交记录不存在")
        if submission.task.creator_id != teacher_id:
            raise PermissionDenied("无权批改该学习路径提交")

        submission.review_status = review_in.review_status
        submission.score = review_in.score
        submission.feedback = review_in.feedback
        submission.follow_up = review_in.follow_up
        submission.reopen_until = review_in.reopen_until
        submission.reviewed_by = teacher_id
        submission.reviewed_at = datetime.now(timezone.utc)
        db.add(submission)

        progress = await LearningPathService._get_or_create_progress(db, submission.task_id, submission.node_id, submission.user_id)
        progress.score = review_in.score
        if review_in.review_status == "approved":
            progress.status = "completed"
            progress.completed_at = progress.completed_at or datetime.now(timezone.utc)
            await LearningPathService._unlock_next_nodes(db, submission.task_id, submission.user_id, submission.node_id)
        elif review_in.review_status in ["rejected", "revise"]:
            progress.status = "reopened"
        db.add(progress)

        await LearningPathService._recalculate_assignee_progress(db, submission.task_id, submission.user_id)
        await db.commit()
        await db.refresh(submission)
        await NotificationService.create_notification(
            db,
            user_id=submission.user_id,
            title="学习路径提交已批改",
            content=f"学习路径「{submission.task.title}」的节点提交已批改。",
            notification_type="learning_path",
            link_url="/student/learning-paths",
        )
        return submission

    @staticmethod
    async def get_class_overview(db: AsyncSession, class_id: UUID, teacher_id: UUID) -> Dict[str, Any]:
        class_group = await LearningPathService.get_class(db, class_id, teacher_id)
        student_ids = [member.user_id for member in class_group.members if member.status == "active"]
        class_info = LearningPathService._class_to_dict(class_group)
        metrics = await LearningPathService._class_metrics(db, class_id, student_ids)
        memory_summary = await LearningPathService._memory_summary(db, student_ids)
        attention_students = await LearningPathService._attention_students(db, student_ids, class_group.members)
        recent_paths = await LearningPathService._recent_class_paths(db, class_id)
        trend = await LearningPathService._class_trend(db, class_id, student_ids, metrics)
        insights = await LearningPathService.refresh_class_insights(db, class_group, student_ids)
        return {
            "class_info": class_info,
            "metrics": metrics,
            "trend": trend,
            "memory_summary": memory_summary,
            "insights": insights,
            "attention_students": attention_students,
            "recent_paths": recent_paths,
        }

    @staticmethod
    async def update_insight_status(
        db: AsyncSession,
        insight_id: UUID,
        teacher_id: UUID,
        status_in: LearningInsightStatusUpdate,
    ) -> Dict[str, Any]:
        valid_statuses = LearningPathService.INSIGHT_VISIBLE_STATUSES | LearningPathService.INSIGHT_CLOSED_STATUSES
        if status_in.status not in valid_statuses:
            raise ValidationError("不支持的洞察状态", code="INVALID_INSIGHT_STATUS")

        result = await db.execute(
            select(LearningInsight).where(and_(LearningInsight.id == insight_id, LearningInsight.deleted_at.is_(None)))
        )
        insight = result.scalars().first()
        if not insight:
            raise NotFoundError("洞察不存在")
        if insight.teacher_id and insight.teacher_id != teacher_id:
            raise PermissionDenied("无权更新该洞察")

        insight.status = status_in.status
        insight.updated_at = datetime.now(timezone.utc)
        db.add(insight)
        await db.commit()
        await db.refresh(insight)
        return LearningPathService._insight_to_dict(insight)

    @staticmethod
    async def get_student_growth(db: AsyncSession, student_id: UUID, requester: User) -> Dict[str, Any]:
        if not any(role in requester.role_codes for role in ["student", "teacher", "admin"]):
            raise PermissionDenied("无权查看成长档案")
        await AccessControlService.ensure_can_access_student(db, requester, student_id)

        user_result = await db.execute(select(User).options(selectinload(User.student_profile)).where(User.id == student_id))
        student = user_result.scalars().first()
        if not student:
            raise NotFoundError("学生不存在")

        path_summaries = await LearningPathService.list_student_paths(db, student_id)
        memory_result = await db.execute(
            select(StudentMemory)
            .where(and_(StudentMemory.user_id == student_id, StudentMemory.status == "active"))
            .order_by(desc(StudentMemory.confidence), desc(StudentMemory.updated_at))
            .limit(8)
        )
        memories = list(memory_result.scalars().all())
        review_result = await db.execute(
            select(DailyReview)
            .where(DailyReview.user_id == student_id)
            .order_by(desc(DailyReview.review_date))
            .limit(7)
        )
        reviews = list(review_result.scalars().all())

        completed_paths = sum(1 for item in path_summaries if item.get("status") == "completed")
        avg_progress = round(sum(float(item.get("avg_progress", 0)) for item in path_summaries) / len(path_summaries), 1) if path_summaries else 0.0
        study_minutes = sum((review.study_stats or {}).get("study_time_minutes", 0) for review in reviews)
        weak_cards = [memory.content for memory in memories if memory.category == "weakness"][:3]

        display_name = user_display_name(student.nickname)
        parent_summary = (
            f"{display_name} 近期共有 {len(path_summaries)} 个学习路径任务，"
            f"平均完成度 {avg_progress}%。近 7 次复盘累计学习约 {study_minutes} 分钟。"
        )
        if weak_cards:
            parent_summary += " 建议持续关注：" + "；".join(weak_cards)

        return {
            "student_id": student_id,
            "profile": {
                "username": student.username,
                "nickname": student.nickname,
                "display_name": display_name,
                "email": student.email,
                "student_profile": {
                    "student_id": student.student_profile.student_id if student.student_profile else None,
                    "grade": student.student_profile.grade if student.student_profile else None,
                    "major": student.student_profile.major if student.student_profile else None,
                    "research_direction": student.student_profile.research_direction if student.student_profile else None,
                },
            },
            "metrics": {
                "path_count": len(path_summaries),
                "completed_paths": completed_paths,
                "avg_progress": avg_progress,
                "recent_study_minutes": study_minutes,
                "memory_count": len(memories),
            },
            "trend": [
                {
                    "date": review.review_date.isoformat(),
                    "study_minutes": (review.study_stats or {}).get("study_time_minutes", 0),
                    "task_completed": (review.task_stats or {}).get("tasks_completed", 0),
                }
                for review in reversed(reviews)
            ],
            "learning_paths": path_summaries[:6],
            "memory_cards": [
                {
                    "id": str(memory.id),
                    "category": memory.category,
                    "memory_type": memory.memory_type,
                    "content": memory.content,
                    "confidence": memory.confidence,
                    "evidence": memory.evidence,
                }
                for memory in memories
            ],
            "parent_summary": parent_summary,
        }

    @staticmethod
    async def _replace_path_graph(
        db: AsyncSession,
        task: LearningPathTask,
        stages: List[LearningPathStageIn],
        nodes: List[LearningPathNodeIn],
        edges: List[LearningPathEdgeIn],
    ) -> None:
        await db.execute(delete(LearningPathResource).where(LearningPathResource.task_id == task.id))
        await db.execute(delete(LearningPathEdge).where(LearningPathEdge.task_id == task.id))
        await db.execute(delete(LearningPathNode).where(LearningPathNode.task_id == task.id))
        await db.execute(delete(LearningPathStage).where(LearningPathStage.task_id == task.id))
        await db.flush()

        stage_records: List[LearningPathStage] = []
        for index, stage_in in enumerate(stages):
            stage = LearningPathStage(
                task_id=task.id,
                title=stage_in.title,
                description=stage_in.description,
                order_index=stage_in.order_index if stage_in.order_index is not None else index,
            )
            db.add(stage)
            stage_records.append(stage)
        await db.flush()

        node_by_key: Dict[str, LearningPathNode] = {}
        for index, node_in in enumerate(nodes):
            key = node_in.key or f"node_{index + 1}"
            stage_order = (node_in.config or {}).get("stage_order", 0)
            stage = stage_records[min(max(int(stage_order or 0), 0), len(stage_records) - 1)] if stage_records else None
            node = LearningPathNode(
                task_id=task.id,
                stage_id=stage.id if stage else None,
                key=key,
                title=node_in.title,
                description=node_in.description,
                node_type=node_in.node_type,
                order_index=node_in.order_index if node_in.order_index is not None else index,
                estimated_minutes=node_in.estimated_minutes,
                required=node_in.required,
                config=node_in.config,
            )
            db.add(node)
            await db.flush()
            node_by_key[key] = node

            for resource_in in node_in.resources:
                db.add(LearningPathService._resource_from_input(task.id, node.id, resource_in))

        await db.flush()

        for edge_in in edges:
            source_node = node_by_key.get(edge_in.source_key)
            target_node = node_by_key.get(edge_in.target_key)
            db.add(LearningPathEdge(
                task_id=task.id,
                source_node_id=source_node.id if source_node else None,
                target_node_id=target_node.id if target_node else None,
                source_key=edge_in.source_key,
                target_key=edge_in.target_key,
            ))

    @staticmethod
    def _resource_from_input(task_id: UUID, node_id: Optional[UUID], resource_in: LearningPathResourceIn) -> LearningPathResource:
        return LearningPathResource(
            task_id=task_id,
            node_id=node_id,
            resource_type=resource_in.resource_type,
            title=resource_in.title,
            url=resource_in.url,
            bv_id=resource_in.bv_id,
            file_id=resource_in.file_id,
            metadata_json=resource_in.metadata,
        )

    @staticmethod
    async def _resolve_assignees(db: AsyncSession, class_id: Optional[UUID], assignee_ids: List[UUID]) -> List[UUID]:
        resolved = set(assignee_ids or [])
        if class_id:
            result = await db.execute(
                select(ClassMember.user_id).where(and_(ClassMember.class_id == class_id, ClassMember.status == "active"))
            )
            resolved.update(result.scalars().all())
        return list(resolved)

    @staticmethod
    async def _assign_students(db: AsyncSession, task: LearningPathTask, student_ids: List[UUID]) -> None:
        if not student_ids:
            return
        now = datetime.now(timezone.utc)
        _, nodes, _, _ = await LearningPathService._load_graph(db, task.id)
        first_node_id = nodes[0].id if nodes else None
        for student_id in student_ids:
            db.add(LearningPathAssignee(
                task_id=task.id,
                user_id=student_id,
                class_id=task.class_id,
                status="not_started",
                progress_percent=0.0,
                assigned_at=now,
            ))
            for node in nodes:
                db.add(LearningNodeProgress(
                    task_id=task.id,
                    node_id=node.id,
                    user_id=student_id,
                    status="available" if node.id == first_node_id else "locked",
                ))

    @staticmethod
    async def _load_graph(db: AsyncSession, task_id: UUID) -> Tuple[List[LearningPathStage], List[LearningPathNode], List[LearningPathEdge], List[LearningPathResource]]:
        stages_result = await db.execute(select(LearningPathStage).where(LearningPathStage.task_id == task_id).order_by(LearningPathStage.order_index.asc()))
        nodes_result = await db.execute(select(LearningPathNode).where(LearningPathNode.task_id == task_id).order_by(LearningPathNode.order_index.asc()))
        edges_result = await db.execute(select(LearningPathEdge).where(LearningPathEdge.task_id == task_id))
        resources_result = await db.execute(select(LearningPathResource).where(LearningPathResource.task_id == task_id))
        return (
            list(stages_result.scalars().all()),
            list(nodes_result.scalars().all()),
            list(edges_result.scalars().all()),
            list(resources_result.scalars().all()),
        )

    @staticmethod
    async def _load_progress_map(db: AsyncSession, task_id: UUID, user_id: Optional[UUID]) -> Dict[UUID, Dict[str, Any]]:
        if not user_id:
            return {}
        result = await db.execute(
            select(LearningNodeProgress).where(and_(LearningNodeProgress.task_id == task_id, LearningNodeProgress.user_id == user_id))
        )
        records = result.scalars().all()
        return {
            record.node_id: {
                "id": str(record.id),
                "status": record.status,
                "score": record.score,
                "started_at": record.started_at.isoformat() if record.started_at else None,
                "submitted_at": record.submitted_at.isoformat() if record.submitted_at else None,
                "completed_at": record.completed_at.isoformat() if record.completed_at else None,
            }
            for record in records
        }

    @staticmethod
    async def _get_or_create_progress(db: AsyncSession, task_id: UUID, node_id: UUID, user_id: UUID) -> LearningNodeProgress:
        result = await db.execute(
            select(LearningNodeProgress).where(
                and_(LearningNodeProgress.task_id == task_id, LearningNodeProgress.node_id == node_id, LearningNodeProgress.user_id == user_id)
            )
        )
        progress = result.scalars().first()
        if progress:
            return progress
        progress = LearningNodeProgress(task_id=task_id, node_id=node_id, user_id=user_id, status="available")
        db.add(progress)
        await db.flush()
        return progress

    @staticmethod
    async def _unlock_next_nodes(db: AsyncSession, task_id: UUID, user_id: UUID, node_id: UUID) -> None:
        node_result = await db.execute(select(LearningPathNode).where(LearningPathNode.id == node_id))
        node = node_result.scalars().first()
        if not node:
            return
        edge_result = await db.execute(select(LearningPathEdge).where(and_(LearningPathEdge.task_id == task_id, LearningPathEdge.source_key == node.key)))
        edges = edge_result.scalars().all()
        for edge in edges:
            if not edge.target_node_id:
                continue
            next_progress = await LearningPathService._get_or_create_progress(db, task_id, edge.target_node_id, user_id)
            if next_progress.status == "locked":
                next_progress.status = "available"
                db.add(next_progress)

    @staticmethod
    async def _recalculate_assignee_progress(db: AsyncSession, task_id: UUID, user_id: UUID) -> None:
        result = await db.execute(
            select(LearningNodeProgress).where(and_(LearningNodeProgress.task_id == task_id, LearningNodeProgress.user_id == user_id))
        )
        progress_records = list(result.scalars().all())
        total = len(progress_records)
        completed = sum(1 for item in progress_records if item.status == "completed")
        percent = round((completed / total) * 100, 1) if total else 0.0

        assignee_result = await db.execute(
            select(LearningPathAssignee).where(and_(LearningPathAssignee.task_id == task_id, LearningPathAssignee.user_id == user_id))
        )
        assignee = assignee_result.scalars().first()
        if assignee:
            assignee.progress_percent = percent
            assignee.status = "completed" if percent >= 100 else "in_progress"
            if percent >= 100 and not assignee.completed_at:
                assignee.completed_at = datetime.now(timezone.utc)
            db.add(assignee)

    @staticmethod
    async def _task_summary(db: AsyncSession, task: LearningPathTask) -> Dict[str, Any]:
        assignee_result = await db.execute(
            select(func.count(LearningPathAssignee.id), func.coalesce(func.avg(LearningPathAssignee.progress_percent), 0))
            .where(LearningPathAssignee.task_id == task.id)
        )
        count, avg_progress = assignee_result.one()
        return {
            "id": task.id,
            "creator_id": task.creator_id,
            "class_id": task.class_id,
            "title": task.title,
            "goal": task.goal,
            "planning_text": task.planning_text,
            "description": task.description,
            "status": task.status,
            "due_date": task.due_date,
            "published_at": task.published_at,
            "created_at": task.created_at,
            "updated_at": task.updated_at,
            "assignee_count": int(count or 0),
            "avg_progress": round(float(avg_progress or 0), 1),
        }

    @staticmethod
    async def _list_assignees(db: AsyncSession, task_id: UUID) -> List[Dict[str, Any]]:
        result = await db.execute(
            select(LearningPathAssignee)
            .options(selectinload(LearningPathAssignee.user))
            .where(LearningPathAssignee.task_id == task_id)
            .order_by(desc(LearningPathAssignee.assigned_at))
        )
        return [
            {
                "id": str(item.id),
                "user_id": str(item.user_id),
                "username": item.user.username,
                "nickname": item.user.nickname,
                "display_name": user_display_name(item.user.nickname),
                "status": item.status,
                "progress_percent": item.progress_percent,
                "assigned_at": item.assigned_at.isoformat() if item.assigned_at else None,
                "completed_at": item.completed_at.isoformat() if item.completed_at else None,
            }
            for item in result.scalars().all()
        ]

    @staticmethod
    async def _list_submissions(db: AsyncSession, task_id: UUID) -> List[Dict[str, Any]]:
        result = await db.execute(
            select(LearningNodeSubmission)
            .options(selectinload(LearningNodeSubmission.user), selectinload(LearningNodeSubmission.node))
            .where(LearningNodeSubmission.task_id == task_id)
            .order_by(desc(LearningNodeSubmission.created_at))
        )
        return [
            {
                "id": str(item.id),
                "task_id": str(item.task_id),
                "node_id": str(item.node_id),
                "node_title": item.node.title if item.node else "",
                "user_id": str(item.user_id),
                "username": item.user.username,
                "nickname": item.user.nickname,
                "display_name": user_display_name(item.user.nickname),
                "content": item.content,
                "attachment_ids": item.attachment_ids or [],
                "review_status": item.review_status,
                "score": item.score,
                "feedback": item.feedback,
                "follow_up": item.follow_up,
                "reviewed_by": str(item.reviewed_by) if item.reviewed_by else None,
                "reviewed_at": item.reviewed_at.isoformat() if item.reviewed_at else None,
                "reopen_until": item.reopen_until.isoformat() if item.reopen_until else None,
                "created_at": item.created_at.isoformat(),
            }
            for item in result.scalars().all()
        ]

    @staticmethod
    def _resource_to_dict(resource: LearningPathResource) -> Dict[str, Any]:
        return {
            "id": resource.id,
            "task_id": resource.task_id,
            "node_id": resource.node_id,
            "resource_type": resource.resource_type,
            "title": resource.title,
            "url": resource.url,
            "bv_id": resource.bv_id,
            "file_id": resource.file_id,
            "metadata": resource.metadata_json,
        }

    @staticmethod
    def _class_to_dict(class_group: ClassGroup) -> Dict[str, Any]:
        members = [
            {
                "id": member.id,
                "user_id": member.user_id,
                "username": member.user.username if member.user else None,
                "nickname": member.user.nickname if member.user else None,
                "display_name": user_display_name(member.user.nickname) if member.user else "未设置姓名",
                "status": member.status,
                "joined_at": member.joined_at,
            }
            for member in class_group.members
        ]
        return {
            "id": class_group.id,
            "teacher_id": class_group.teacher_id,
            "name": class_group.name,
            "description": class_group.description,
            "grade": class_group.grade,
            "subject": class_group.subject,
            "status": class_group.status,
            "created_at": class_group.created_at,
            "member_count": len(members),
            "members": members,
        }

    @staticmethod
    async def _class_metrics(db: AsyncSession, class_id: UUID, student_ids: List[UUID]) -> Dict[str, Any]:
        if not student_ids:
            return {"student_count": 0, "avg_progress": 0, "active_paths": 0, "submitted_nodes": 0, "memory_count": 0}

        progress_result = await db.execute(
            select(func.coalesce(func.avg(LearningPathAssignee.progress_percent), 0), func.count(LearningPathAssignee.id))
            .where(LearningPathAssignee.class_id == class_id)
        )
        avg_progress, active_paths = progress_result.one()
        submission_result = await db.execute(select(func.count(LearningNodeSubmission.id)).where(LearningNodeSubmission.user_id.in_(student_ids)))
        memory_result = await db.execute(
            select(func.count(StudentMemory.id)).where(and_(StudentMemory.user_id.in_(student_ids), StudentMemory.status == "active"))
        )
        return {
            "student_count": len(student_ids),
            "avg_progress": round(float(avg_progress or 0), 1),
            "active_paths": int(active_paths or 0),
            "submitted_nodes": int(submission_result.scalar() or 0),
            "memory_count": int(memory_result.scalar() or 0),
        }

    @staticmethod
    async def _memory_summary(db: AsyncSession, student_ids: List[UUID]) -> Dict[str, Any]:
        if not student_ids:
            return {"top_categories": [], "summary": "班级暂无学生数据。"}
        result = await db.execute(
            select(StudentMemory.category, func.count(StudentMemory.id))
            .where(and_(StudentMemory.user_id.in_(student_ids), StudentMemory.status == "active"))
            .group_by(StudentMemory.category)
            .order_by(desc(func.count(StudentMemory.id)))
            .limit(6)
        )
        categories = [{"category": row[0], "count": int(row[1])} for row in result.all()]
        if categories:
            summary = "班级 Memory 主要集中在：" + "、".join(f"{item['category']}({item['count']})" for item in categories[:3])
        else:
            summary = "班级尚未沉淀足够 Memory，建议先推动学生完成每日复盘与路径提交。"
        return {"top_categories": categories, "summary": summary}

    @staticmethod
    async def refresh_class_insights(db: AsyncSession, class_group: ClassGroup, student_ids: List[UUID]) -> List[Dict[str, Any]]:
        if not student_ids:
            return []

        candidates = await LearningPathService._build_class_insight_candidates(db, class_group, student_ids)
        existing_result = await db.execute(
            select(LearningInsight)
            .where(
                and_(
                    LearningInsight.class_id == class_group.id,
                    LearningInsight.scope == "class",
                    LearningInsight.deleted_at.is_(None),
                )
            )
        )
        existing_items = list(existing_result.scalars().all())
        existing_by_fingerprint = {
            item.source_fingerprint: item
            for item in existing_items
            if item.source_fingerprint
        }

        now = datetime.now(timezone.utc)
        active_fingerprints = set()
        for candidate in candidates[:8]:
            fingerprint = candidate["source_fingerprint"]
            active_fingerprints.add(fingerprint)
            existing = existing_by_fingerprint.get(fingerprint)
            if existing and existing.status in LearningPathService.INSIGHT_CLOSED_STATUSES:
                continue

            if not existing:
                existing = LearningInsight(status="new", generated_at=now, **candidate)
            else:
                for field, value in candidate.items():
                    setattr(existing, field, value)
                existing.generated_at = now
                existing.updated_at = now
            db.add(existing)

        for insight in existing_items:
            if (
                insight.source == "system"
                and insight.status in LearningPathService.INSIGHT_VISIBLE_STATUSES
                and insight.source_fingerprint not in active_fingerprints
            ):
                insight.status = "resolved"
                insight.updated_at = now
                db.add(insight)

        await db.flush()
        result = await db.execute(
            select(LearningInsight)
            .where(
                and_(
                    LearningInsight.class_id == class_group.id,
                    LearningInsight.scope == "class",
                    LearningInsight.status.in_(LearningPathService.INSIGHT_VISIBLE_STATUSES),
                    LearningInsight.deleted_at.is_(None),
                )
            )
            .order_by(desc(LearningInsight.generated_at), desc(LearningInsight.created_at))
            .limit(8)
        )
        return [LearningPathService._insight_to_dict(item) for item in result.scalars().all()]

    @staticmethod
    async def _build_class_insight_candidates(
        db: AsyncSession,
        class_group: ClassGroup,
        student_ids: List[UUID],
    ) -> List[Dict[str, Any]]:
        name_map = {
            member.user_id: user_display_name(member.user.nickname) if member.user else "未设置姓名"
            for member in class_group.members
        }
        candidates: List[Dict[str, Any]] = []
        candidates.extend(await LearningPathService._memory_content_insight_candidates(db, class_group, student_ids, name_map))
        progress_candidate = await LearningPathService._path_progress_insight_candidate(db, class_group, student_ids, name_map)
        pending_candidate = await LearningPathService._pending_submission_insight_candidate(db, class_group, student_ids, name_map)
        for item in [progress_candidate, pending_candidate]:
            if item:
                candidates.append(item)

        severity_order = {"high": 0, "medium": 1, "low": 2}
        return sorted(
            candidates,
            key=lambda item: (
                severity_order.get(item.get("severity", "medium"), 1),
                -len(item.get("affected_student_ids") or []),
                item.get("title", ""),
            ),
        )

    @staticmethod
    async def _memory_content_insight_candidates(
        db: AsyncSession,
        class_group: ClassGroup,
        student_ids: List[UUID],
        name_map: Dict[UUID, str],
    ) -> List[Dict[str, Any]]:
        result = await db.execute(
            select(StudentMemory)
            .where(and_(StudentMemory.user_id.in_(student_ids), StudentMemory.status == "active"))
            .order_by(desc(StudentMemory.confidence), desc(StudentMemory.updated_at))
            .limit(120)
        )
        groups: Dict[str, Dict[str, Any]] = {}
        for memory in result.scalars().all():
            content = (memory.content or "").strip()
            if not content:
                continue
            category = memory.category or "observation"
            normalized = LearningPathService._normalize_insight_key(content)
            key = f"{category}:{normalized[:120]}"
            bucket = groups.setdefault(
                key,
                {
                    "category": category,
                    "content": content,
                    "memories": [],
                    "student_ids": set(),
                    "confidence": 0.0,
                },
            )
            bucket["memories"].append(memory)
            bucket["student_ids"].add(memory.user_id)
            bucket["confidence"] = max(float(memory.confidence or 0), bucket["confidence"])

        candidates = []
        risk_categories = {"weakness", "challenge", "knowledge_gap"}
        actionable_categories = risk_categories | {"goal", "study_habit"}
        for key, bucket in groups.items():
            affected_ids = list(bucket["student_ids"])
            category = bucket["category"]
            if category not in actionable_categories and len(affected_ids) < 2:
                continue

            label = LearningPathService.MEMORY_CATEGORY_LABELS.get(category, category)
            names = [name_map.get(student_id, "未设置姓名") for student_id in affected_ids[:4]]
            content = bucket["content"]
            affected_count = len(affected_ids)
            severity = "high" if category in risk_categories and affected_count >= 3 else "medium"
            if category not in risk_categories and affected_count < 2:
                severity = "low"
            title_prefix = f"{affected_count} 名学生出现相近{label}" if affected_count > 1 else f"{names[0]}的{label}"
            title = f"{title_prefix}：{LearningPathService._short_text(content, 34)}"
            summary = f"{'、'.join(names)} 的{label}内容指向：{content}"

            memories = bucket["memories"][:4]
            evidence = [
                {
                    "source_type": "student_memory",
                    "source_id": str(memory.id),
                    "student_id": str(memory.user_id),
                    "student_name": name_map.get(memory.user_id, "未设置姓名"),
                    "content": LearningPathService._memory_evidence_text(memory),
                    "occurred_at": memory.updated_at.isoformat() if memory.updated_at else None,
                }
                for memory in memories
            ]
            actions = [
                {
                    "action_type": "create_targeted_path",
                    "label": "生成针对性路径",
                    "payload": {"category": category, "content": content, "student_ids": [str(item) for item in affected_ids]},
                },
                {
                    "action_type": "draft_feedback",
                    "label": "生成反馈草稿",
                    "payload": {"student_ids": [str(item) for item in affected_ids], "focus": content},
                },
            ]
            candidates.append({
                "scope": "class",
                "class_id": class_group.id,
                "student_id": None,
                "teacher_id": class_group.teacher_id,
                "title": title,
                "insight_type": "memory_pattern",
                "severity": severity,
                "summary": summary,
                "affected_student_ids": [str(item) for item in affected_ids],
                "evidence": evidence,
                "suggested_actions": actions,
                "source": "system",
                "source_fingerprint": LearningPathService._fingerprint(class_group.id, "memory", key),
            })

        return candidates[:6]

    @staticmethod
    async def _path_progress_insight_candidate(
        db: AsyncSession,
        class_group: ClassGroup,
        student_ids: List[UUID],
        name_map: Dict[UUID, str],
    ) -> Optional[Dict[str, Any]]:
        avg_progress = func.coalesce(func.avg(LearningPathAssignee.progress_percent), 0)
        result = await db.execute(
            select(LearningPathAssignee.user_id, avg_progress, func.count(LearningPathAssignee.id))
            .where(
                and_(
                    LearningPathAssignee.class_id == class_group.id,
                    LearningPathAssignee.user_id.in_(student_ids),
                    LearningPathAssignee.status != "completed",
                )
            )
            .group_by(LearningPathAssignee.user_id)
            .having(avg_progress < 60)
            .order_by(avg_progress.asc())
            .limit(8)
        )
        rows = result.all()
        if not rows:
            return None

        affected_ids = [row[0] for row in rows]
        evidence = [
            {
                "source_type": "learning_path_progress",
                "student_id": str(user_id),
                "student_name": name_map.get(user_id, "未设置姓名"),
                "content": f"平均路径进度 {round(float(progress or 0), 1)}%，涉及 {int(task_count or 0)} 个未完成路径任务。",
                "occurred_at": datetime.now(timezone.utc).isoformat(),
            }
            for user_id, progress, task_count in rows[:5]
        ]
        summary = "重点跟进：" + "、".join(
            f"{name_map.get(user_id, '未设置姓名')}（{round(float(progress or 0), 1)}%）"
            for user_id, progress, _ in rows[:5]
        )
        return {
            "scope": "class",
            "class_id": class_group.id,
            "student_id": None,
            "teacher_id": class_group.teacher_id,
            "title": f"{len(affected_ids)} 名学生学习路径推进低于 60%",
            "insight_type": "progress_risk",
            "severity": "high" if len(affected_ids) >= 3 else "medium",
            "summary": summary,
            "affected_student_ids": [str(item) for item in affected_ids],
            "evidence": evidence,
            "suggested_actions": [
                {
                    "action_type": "send_reminder",
                    "label": "生成跟进提醒",
                    "payload": {"student_ids": [str(item) for item in affected_ids]},
                },
                {
                    "action_type": "create_checkpoint",
                    "label": "安排阶段检查",
                    "payload": {"class_id": str(class_group.id), "student_ids": [str(item) for item in affected_ids]},
                },
            ],
            "source": "system",
            "source_fingerprint": LearningPathService._fingerprint(class_group.id, "progress", ",".join(sorted(str(item) for item in affected_ids))),
        }

    @staticmethod
    async def _pending_submission_insight_candidate(
        db: AsyncSession,
        class_group: ClassGroup,
        student_ids: List[UUID],
        name_map: Dict[UUID, str],
    ) -> Optional[Dict[str, Any]]:
        result = await db.execute(
            select(LearningNodeSubmission, LearningPathTask.title)
            .join(LearningPathTask, LearningPathTask.id == LearningNodeSubmission.task_id)
            .where(
                and_(
                    LearningPathTask.class_id == class_group.id,
                    LearningNodeSubmission.user_id.in_(student_ids),
                    LearningNodeSubmission.review_status == "pending",
                    LearningPathTask.deleted_at.is_(None),
                )
            )
            .order_by(desc(LearningNodeSubmission.created_at))
            .limit(12)
        )
        rows = result.all()
        if not rows:
            return None

        affected_ids = sorted({submission.user_id for submission, _ in rows}, key=lambda item: name_map.get(item, ""))
        task_titles = list(dict.fromkeys(title for _, title in rows if title))[:3]
        evidence = [
            {
                "source_type": "learning_submission",
                "source_id": str(submission.id),
                "student_id": str(submission.user_id),
                "student_name": name_map.get(submission.user_id, "未设置姓名"),
                "content": f"提交「{title or '学习路径节点'}」等待批改。",
                "occurred_at": submission.created_at.isoformat() if submission.created_at else None,
            }
            for submission, title in rows[:5]
        ]
        return {
            "scope": "class",
            "class_id": class_group.id,
            "student_id": None,
            "teacher_id": class_group.teacher_id,
            "title": f"{len(rows)} 份学习路径节点提交等待批改",
            "insight_type": "review_backlog",
            "severity": "high" if len(rows) >= 8 else "medium",
            "summary": f"待处理提交集中在：{'、'.join(task_titles) if task_titles else '学习路径节点'}。",
            "affected_student_ids": [str(item) for item in affected_ids],
            "evidence": evidence,
            "suggested_actions": [
                {
                    "action_type": "open_review_queue",
                    "label": "进入批改队列",
                    "payload": {"class_id": str(class_group.id)},
                }
            ],
            "source": "system",
            "source_fingerprint": LearningPathService._fingerprint(class_group.id, "pending_submission", len(rows), ",".join(str(item) for item in affected_ids)),
        }

    @staticmethod
    def _insight_to_dict(insight: LearningInsight) -> Dict[str, Any]:
        return {
            "id": insight.id,
            "scope": insight.scope,
            "class_id": insight.class_id,
            "student_id": insight.student_id,
            "teacher_id": insight.teacher_id,
            "title": insight.title,
            "insight_type": insight.insight_type,
            "severity": insight.severity,
            "summary": insight.summary,
            "affected_student_ids": insight.affected_student_ids or [],
            "evidence": insight.evidence or [],
            "suggested_actions": insight.suggested_actions or [],
            "status": insight.status,
            "source": insight.source,
            "source_fingerprint": insight.source_fingerprint,
            "generated_at": insight.generated_at,
            "created_at": insight.created_at,
            "updated_at": insight.updated_at,
        }

    @staticmethod
    def _memory_evidence_text(memory: StudentMemory) -> str:
        evidence = memory.evidence
        if isinstance(evidence, dict):
            for key in ["content", "text", "summary", "message"]:
                value = evidence.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()
        if isinstance(evidence, list) and evidence:
            first = evidence[0]
            if isinstance(first, dict):
                for key in ["content", "text", "summary", "message"]:
                    value = first.get(key)
                    if isinstance(value, str) and value.strip():
                        return value.strip()
            if isinstance(first, str) and first.strip():
                return first.strip()
        return memory.content or ""

    @staticmethod
    def _normalize_insight_key(text: str) -> str:
        return re.sub(r"\s+", "", text).strip().lower()

    @staticmethod
    def _short_text(text: str, limit: int) -> str:
        compact = re.sub(r"\s+", " ", text or "").strip()
        if len(compact) <= limit:
            return compact
        return compact[:limit] + "..."

    @staticmethod
    def _fingerprint(*parts: Any) -> str:
        raw = "|".join(str(part) for part in parts)
        return hashlib.sha1(raw.encode("utf-8")).hexdigest()

    @staticmethod
    async def _attention_students(db: AsyncSession, student_ids: List[UUID], members: List[ClassMember]) -> List[Dict[str, Any]]:
        if not student_ids:
            return []
        progress_result = await db.execute(
            select(LearningPathAssignee.user_id, func.coalesce(func.avg(LearningPathAssignee.progress_percent), 0))
            .where(LearningPathAssignee.user_id.in_(student_ids))
            .group_by(LearningPathAssignee.user_id)
        )
        progress_map = {row[0]: float(row[1] or 0) for row in progress_result.all()}

        weakness_result = await db.execute(
            select(StudentMemory.user_id, func.count(StudentMemory.id))
            .where(
                and_(
                    StudentMemory.user_id.in_(student_ids),
                    StudentMemory.status == "active",
                    StudentMemory.category == "weakness",
                )
            )
            .group_by(StudentMemory.user_id)
        )
        weakness_map = {row[0]: int(row[1] or 0) for row in weakness_result.all()}

        items = []
        for member in members:
            assignee_progress = round(progress_map.get(member.user_id, 0.0), 1)
            weakness_count = weakness_map.get(member.user_id, 0)
            if weakness_count > 0 and assignee_progress < 60:
                reason = f"路径进度 {assignee_progress}%，且有 {weakness_count} 条薄弱项 Memory"
            elif assignee_progress < 60:
                reason = f"路径平均进度 {assignee_progress}%，建议跟进节点提交"
            elif weakness_count > 0:
                reason = f"有 {weakness_count} 条薄弱项 Memory，建议安排针对性反馈"
            else:
                continue
            items.append({
                "user_id": str(member.user_id),
                "name": user_display_name(member.user.nickname) if member.user else "未设置姓名",
                "reason": reason,
                "progress_percent": assignee_progress,
            })
        return sorted(items, key=lambda item: (item["progress_percent"], item["name"]))[:5]

    @staticmethod
    async def _recent_class_paths(db: AsyncSession, class_id: UUID) -> List[Dict[str, Any]]:
        result = await db.execute(
            select(LearningPathTask)
            .where(and_(LearningPathTask.class_id == class_id, LearningPathTask.deleted_at.is_(None)))
            .order_by(desc(LearningPathTask.created_at))
            .limit(5)
        )
        tasks = result.scalars().all()
        return [await LearningPathService._task_summary(db, task) for task in tasks]

    @staticmethod
    async def _class_trend(db: AsyncSession, class_id: UUID, student_ids: List[UUID], metrics: Dict[str, Any]) -> List[Dict[str, Any]]:
        today = datetime.now(timezone.utc).date()
        days = [today - timedelta(days=6 - index) for index in range(7)]
        if not student_ids:
            return [
                {"date": day.isoformat(), "avg_progress": 0, "active_students": 0, "memory_count": 0}
                for day in days
            ]

        review_result = await db.execute(
            select(DailyReview)
            .where(and_(DailyReview.user_id.in_(student_ids), DailyReview.review_date >= days[0], DailyReview.review_date <= days[-1]))
        )
        reviews_by_day: Dict[Any, List[DailyReview]] = {}
        for review in review_result.scalars().all():
            reviews_by_day.setdefault(review.review_date, []).append(review)

        memory_result = await db.execute(
            select(func.date(StudentMemory.created_at), func.count(StudentMemory.id))
            .where(
                and_(
                    StudentMemory.user_id.in_(student_ids),
                    StudentMemory.status == "active",
                    StudentMemory.created_at >= datetime(days[0].year, days[0].month, days[0].day, tzinfo=timezone.utc),
                )
            )
            .group_by(func.date(StudentMemory.created_at))
        )
        memory_by_day = {row[0]: int(row[1] or 0) for row in memory_result.all()}
        current_progress = round(float(metrics.get("avg_progress", 0)), 1)

        return [
            {
                "date": day.isoformat(),
                "avg_progress": current_progress,
                "active_students": len({review.user_id for review in reviews_by_day.get(day, [])}),
                "memory_count": memory_by_day.get(day, 0),
            }
            for day in days
        ]
