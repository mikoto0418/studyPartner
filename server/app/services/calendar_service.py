from datetime import datetime, timezone, timedelta
from typing import Any, List, Optional
from uuid import UUID
from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.calendar_event import CalendarEvent
from app.models.task import Task, TaskAssignee
from app.models.user import User
from app.schemas.calendar_event import CalendarEventCreate, CalendarEventUpdate
from app.core.exceptions import NotFoundError, PermissionDenied
from app.services.access_control import AccessControlService

class CalendarService:
    @staticmethod
    async def get_event(db: AsyncSession, event_id: UUID, user_id: UUID) -> Optional[CalendarEvent]:
        result = await db.execute(
            select(CalendarEvent).where(
                and_(
                    CalendarEvent.id == event_id,
                    CalendarEvent.user_id == user_id,
                    CalendarEvent.deleted_at.is_(None)
                )
            )
        )
        return result.scalars().first()

    @staticmethod
    async def list_events(
        db: AsyncSession,
        user_id: UUID,
        start_time: datetime,
        end_time: datetime
    ) -> List[Any]:
        # Fetch events overlapping with [start_time, end_time]
        query = select(CalendarEvent).where(
            and_(
                CalendarEvent.user_id == user_id,
                CalendarEvent.deleted_at.is_(None),
                # Event starts before range ends, and ends after range starts
                CalendarEvent.start_time <= end_time,
                CalendarEvent.end_time >= start_time
            )
        ).order_by(CalendarEvent.start_time.asc())
        
        result = await db.execute(query)
        events: List[Any] = list(result.scalars().all())

        task_query = (
            select(Task, TaskAssignee.status)
            .join(TaskAssignee, Task.id == TaskAssignee.task_id)
            .where(
                and_(
                    TaskAssignee.user_id == user_id,
                    Task.deleted_at.is_(None),
                    Task.due_date.is_not(None),
                    Task.due_date >= start_time,
                    Task.due_date <= end_time,
                )
            )
        )
        task_rows = (await db.execute(task_query)).all()
        priority_colors = {
            "urgent": "#ef4444",
            "high": "#f59e0b",
            "medium": "#2563eb",
            "low": "#71717a",
        }

        for task, assignee_status in task_rows:
            due_time = task.due_date
            event_start = due_time.replace(hour=0, minute=0, second=0, microsecond=0)
            event_end = event_start + timedelta(days=1)
            events.append({
                "id": task.id,
                "user_id": user_id,
                "created_by": task.creator_id,
                "title": task.title,
                "description": task.description,
                "event_type": "teacher_assigned",
                "status": assignee_status,
                "start_time": event_start,
                "end_time": event_end,
                "all_day": True,
                "color": priority_colors.get(task.priority, "#2563eb"),
                "related_task_id": task.id,
                "related_countdown_id": None,
                "created_at": task.created_at,
                "updated_at": task.updated_at,
            })

        return sorted(events, key=lambda item: item["start_time"] if isinstance(item, dict) else item.start_time)

    @staticmethod
    async def create_event(
        db: AsyncSession, creator: User, event_in: CalendarEventCreate
    ) -> CalendarEvent:
        target_user_id = event_in.user_id if event_in.user_id else creator.id
        if target_user_id != creator.id:
            if "student" in creator.role_codes:
                raise PermissionDenied("学生只能为自己创建日程")
            await AccessControlService.ensure_can_access_student(db, creator, target_user_id)

        db_event = CalendarEvent(
            user_id=target_user_id,
            created_by=creator.id,
            title=event_in.title,
            description=event_in.description,
            event_type=event_in.event_type,
            status=event_in.status,
            start_time=event_in.start_time,
            end_time=event_in.end_time,
            all_day=event_in.all_day,
            color=event_in.color,
            related_task_id=event_in.related_task_id,
            related_countdown_id=event_in.related_countdown_id
        )
        db.add(db_event)
        await db.commit()
        await db.refresh(db_event)
        return db_event

    @classmethod
    async def update_event(
        cls, db: AsyncSession, event_id: UUID, user_id: UUID, event_in: CalendarEventUpdate
    ) -> CalendarEvent:
        db_event = await cls.get_event(db, event_id, user_id)
        if not db_event:
            raise NotFoundError("日程事件不存在")

        update_data = event_in.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_event, field, value)

        db_event.updated_at = datetime.now(timezone.utc)
        db.add(db_event)
        await db.commit()
        await db.refresh(db_event)
        return db_event

    @classmethod
    async def delete_event(cls, db: AsyncSession, event_id: UUID, user_id: UUID) -> bool:
        db_event = await cls.get_event(db, event_id, user_id)
        if not db_event:
            raise NotFoundError("日程事件不存在")
            
        db_event.deleted_at = datetime.now(timezone.utc)
        db.add(db_event)
        await db.commit()
        return True
