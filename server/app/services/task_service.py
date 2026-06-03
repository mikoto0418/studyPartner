from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.models.task import Task, TaskAssignee, TaskSubmission
from app.schemas.task import TaskCreate, TaskSubmissionCreate, TaskSubmissionReview
from app.core.exceptions import NotFoundError, ValidationError

class TaskService:
    @staticmethod
    async def get_task(db: AsyncSession, task_id: UUID) -> Optional[Task]:
        result = await db.execute(
            select(Task).where(and_(Task.id == task_id, Task.deleted_at.is_(None)))
        )
        return result.scalars().first()

    @staticmethod
    async def create_task(db: AsyncSession, creator_id: UUID, task_in: TaskCreate) -> Task:
        db_task = Task(
            creator_id=creator_id,
            title=task_in.title,
            description=task_in.description,
            priority=task_in.priority,
            status="in_progress",
            start_date=task_in.start_date or datetime.now(timezone.utc),
            due_date=task_in.due_date,
            attachment_ids=task_in.attachment_ids
        )
        db.add(db_task)
        await db.flush()

        # Link assignees
        for student_id in task_in.assignee_ids:
            assignee = TaskAssignee(
                task_id=db_task.id,
                user_id=student_id,
                status="in_progress",
                assigned_at=datetime.now(timezone.utc)
            )
            db.add(assignee)

        await db.commit()
        await db.refresh(db_task)
        return db_task

    @staticmethod
    async def list_student_tasks(db: AsyncSession, user_id: UUID) -> List[dict]:
        # Return tasks assigned to the student along with their assignment status
        query = (
            select(Task, TaskAssignee.status, TaskAssignee.completed_at)
            .join(TaskAssignee, Task.id == TaskAssignee.task_id)
            .where(and_(TaskAssignee.user_id == user_id, Task.deleted_at.is_(None)))
            .order_by(Task.due_date.asc())
        )
        result = await db.execute(query)
        rows = result.all()

        output = []
        for task, status, completed_at in rows:
            t_dict = {
                "id": task.id,
                "title": task.title,
                "description": task.description,
                "priority": task.priority,
                "due_date": task.due_date,
                "status": status,  # Use assignee status
                "completed_at": completed_at,
                "attachment_ids": task.attachment_ids
            }
            output.append(t_dict)
        return output

    @staticmethod
    async def submit_task(
        db: AsyncSession, task_id: UUID, user_id: UUID, submission_in: TaskSubmissionCreate
    ) -> TaskSubmission:
        # Get assignee link
        assignee_result = await db.execute(
            select(TaskAssignee).where(
                and_(TaskAssignee.task_id == task_id, TaskAssignee.user_id == user_id)
            )
        )
        assignee = assignee_result.scalars().first()
        if not assignee:
            raise ValidationError("你没有被指派该任务，无法提交")

        # Create submission
        submission = TaskSubmission(
            task_id=task_id,
            assignee_id=assignee.id,
            user_id=user_id,
            content=submission_in.content,
            attachment_ids=submission_in.attachment_ids
        )
        db.add(submission)

        # Update assignee status to submitted
        assignee.status = "submitted"
        db.add(assignee)

        await db.commit()
        await db.refresh(submission)
        return submission

    @staticmethod
    async def review_submission(
        db: AsyncSession, submission_id: UUID, reviewer_id: UUID, review_in: TaskSubmissionReview
    ) -> TaskSubmission:
        result = await db.execute(
            select(TaskSubmission)
            .options(selectinload(TaskSubmission.task))
            .where(TaskSubmission.id == submission_id)
        )
        submission = result.scalars().first()
        if not submission:
            raise NotFoundError("任务提交记录不存在")

        # Get assignee link
        assignee_result = await db.execute(
            select(TaskAssignee).where(TaskAssignee.id == submission.assignee_id)
        )
        assignee = assignee_result.scalars().first()

        submission.feedback = review_in.feedback
        submission.reviewed_by = reviewer_id
        submission.reviewed_at = datetime.now(timezone.utc)
        db.add(submission)

        if assignee:
            assignee.status = review_in.status # completed or rejected
            if review_in.status == "completed":
                assignee.completed_at = datetime.now(timezone.utc)
            db.add(assignee)

        await db.commit()
        await db.refresh(submission)
        return submission

    @staticmethod
    async def list_teacher_created_tasks(db: AsyncSession, teacher_id: UUID) -> List[Task]:
        result = await db.execute(
            select(Task)
            .where(and_(Task.creator_id == teacher_id, Task.deleted_at.is_(None)))
            .order_by(Task.created_at.desc())
        )
        return list(result.scalars().all())

    @staticmethod
    async def get_task_details(db: AsyncSession, task_id: UUID) -> Optional[dict]:
        task = await TaskService.get_task(db, task_id)
        if not task:
            return None
        
        # Load assignees with users
        assignees_query = (
            select(TaskAssignee)
            .options(selectinload(TaskAssignee.user))
            .where(TaskAssignee.task_id == task_id)
        )
        assignees_res = await db.execute(assignees_query)
        assignees = assignees_res.scalars().all()
        
        # Load submissions with users
        submissions_query = (
            select(TaskSubmission)
            .options(selectinload(TaskSubmission.user))
            .where(TaskSubmission.task_id == task_id)
        )
        submissions_res = await db.execute(submissions_query)
        submissions = submissions_res.scalars().all()
        
        return {
            "task": {
                "id": str(task.id),
                "title": task.title,
                "description": task.description,
                "priority": task.priority,
                "status": task.status,
                "start_date": task.start_date.isoformat() if task.start_date else None,
                "due_date": task.due_date.isoformat() if task.due_date else None,
                "attachment_ids": [str(x) for x in task.attachment_ids] if task.attachment_ids else [],
                "created_at": task.created_at.isoformat(),
            },
            "assignees": [
                {
                    "id": str(a.id),
                    "user_id": str(a.user_id),
                    "username": a.user.username,
                    "nickname": a.user.nickname,
                    "status": a.status,
                    "assigned_at": a.assigned_at.isoformat() if a.assigned_at else None,
                    "completed_at": a.completed_at.isoformat() if a.completed_at else None,
                }
                for a in assignees
            ],
            "submissions": [
                {
                    "id": str(s.id),
                    "assignee_id": str(s.assignee_id),
                    "user_id": str(s.user_id),
                    "username": s.user.username,
                    "nickname": s.user.nickname,
                    "content": s.content,
                    "attachment_ids": [str(x) for x in s.attachment_ids] if s.attachment_ids else [],
                    "feedback": s.feedback,
                    "reviewed_by": str(s.reviewed_by) if s.reviewed_by else None,
                    "reviewed_at": s.reviewed_at.isoformat() if s.reviewed_at else None,
                    "created_at": s.created_at.isoformat(),
                }
                for s in submissions
            ]
        }

