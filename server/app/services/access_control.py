from typing import List, Optional
from uuid import UUID

from sqlalchemy import and_, cast, func, literal, or_, select, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import PermissionDenied
from app.models.learning_path import ClassGroup, ClassMember, ClassTeacher, LearningPathAssignee, LearningPathTask
from app.models.assessment import AssessmentPaper
from app.models.task import Task, TaskAssignee
from app.models.user import User


class AccessControlService:
    @staticmethod
    def class_scope(teacher_id: UUID):
        return and_(
            ClassGroup.deleted_at.is_(None),
            or_(
                ClassGroup.teacher_id == teacher_id,
                ClassGroup.id.in_(
                    select(ClassTeacher.class_id).where(ClassTeacher.teacher_id == teacher_id)
                ),
            ),
        )

    @classmethod
    def paper_scope(cls, teacher_id: UUID):
        # 协管只共享已发布且全部目标班级均有权管理的试卷。
        # 不共享同事的草稿、个人指派试卷或其他班级的成绩。
        managed_ids = (
            select(func.jsonb_agg(cast(ClassGroup.id, String)))
            .where(cls.class_scope(teacher_id))
            .scalar_subquery()
        )
        target_ids = AssessmentPaper.publish_target["ids"]
        return or_(
            AssessmentPaper.creator_id == teacher_id,
            and_(
                AssessmentPaper.parse_status == "published",
                AssessmentPaper.publish_target["type"].astext == "class",
                func.jsonb_typeof(target_ids) == "array",
                target_ids != literal([], type_=JSONB),
                target_ids.contained_by(func.coalesce(managed_ids, literal([], type_=JSONB))),
                # 白名单可以扩大受众，因此带白名单的卷保持创建人独享。
                or_(
                    AssessmentPaper.publish_target["whitelist"].is_(None),
                    AssessmentPaper.publish_target["whitelist"] == literal([], type_=JSONB),
                ),
            ),
        )

    @staticmethod
    def is_admin(user: User) -> bool:
        return "admin" in user.role_codes

    @staticmethod
    def is_teacher(user: User) -> bool:
        return "teacher" in user.role_codes

    @staticmethod
    def is_student(user: User) -> bool:
        return "student" in user.role_codes

    @classmethod
    async def can_access_student(cls, db: AsyncSession, requester: User, student_id: UUID) -> bool:
        if cls.is_admin(requester):
            return True
        if cls.is_student(requester) and requester.id == student_id:
            return True
        if not cls.is_teacher(requester):
            return False

        class_stmt = (
            select(ClassMember.id)
            .join(ClassGroup, ClassMember.class_id == ClassGroup.id)
            .where(
                and_(
                    cls.class_scope(requester.id),
                    ClassGroup.deleted_at.is_(None),
                    ClassMember.user_id == student_id,
                    ClassMember.status == "active",
                    ClassMember.deleted_at.is_(None),
                )
            )
            .limit(1)
        )
        if (await db.execute(class_stmt)).scalar_one_or_none():
            return True

        task_stmt = (
            select(TaskAssignee.id)
            .join(Task, TaskAssignee.task_id == Task.id)
            .where(
                and_(
                    Task.creator_id == requester.id,
                    Task.deleted_at.is_(None),
                    TaskAssignee.user_id == student_id,
                )
            )
            .limit(1)
        )
        if (await db.execute(task_stmt)).scalar_one_or_none():
            return True

        path_stmt = (
            select(LearningPathAssignee.id)
            .join(LearningPathTask, LearningPathAssignee.task_id == LearningPathTask.id)
            .where(
                and_(
                    LearningPathTask.creator_id == requester.id,
                    LearningPathTask.deleted_at.is_(None),
                    LearningPathAssignee.user_id == student_id,
                )
            )
            .limit(1)
        )
        return bool((await db.execute(path_stmt)).scalar_one_or_none())

    @classmethod
    async def ensure_can_access_student(cls, db: AsyncSession, requester: User, student_id: UUID) -> None:
        if not await cls.can_access_student(db, requester, student_id):
            raise PermissionDenied("无权访问该学生数据")

    @classmethod
    async def accessible_student_ids(cls, db: AsyncSession, requester: User) -> Optional[List[UUID]]:
        if cls.is_admin(requester):
            return None
        if cls.is_student(requester):
            return [requester.id]
        if not cls.is_teacher(requester):
            return []

        ids: set[UUID] = set()

        class_stmt = (
            select(ClassMember.user_id)
            .join(ClassGroup, ClassMember.class_id == ClassGroup.id)
            .where(
                and_(
                    cls.class_scope(requester.id),
                    ClassGroup.deleted_at.is_(None),
                    ClassMember.status == "active",
                    ClassMember.deleted_at.is_(None),
                )
            )
        )
        ids.update((await db.execute(class_stmt)).scalars().all())

        task_stmt = (
            select(TaskAssignee.user_id)
            .join(Task, TaskAssignee.task_id == Task.id)
            .where(and_(Task.creator_id == requester.id, Task.deleted_at.is_(None)))
        )
        ids.update((await db.execute(task_stmt)).scalars().all())

        path_stmt = (
            select(LearningPathAssignee.user_id)
            .join(LearningPathTask, LearningPathAssignee.task_id == LearningPathTask.id)
            .where(and_(LearningPathTask.creator_id == requester.id, LearningPathTask.deleted_at.is_(None)))
        )
        ids.update((await db.execute(path_stmt)).scalars().all())
        return list(ids)
