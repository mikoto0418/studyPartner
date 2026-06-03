from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID
from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.calendar_event import CalendarEvent
from app.schemas.calendar_event import CalendarEventCreate, CalendarEventUpdate
from app.core.exceptions import NotFoundError

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
    ) -> List[CalendarEvent]:
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
        return list(result.scalars().all())

    @staticmethod
    async def create_event(
        db: AsyncSession, creator_id: UUID, event_in: CalendarEventCreate
    ) -> CalendarEvent:
        # If user_id is specified in schema (meaning a teacher is assigning it to a student),
        # use that user_id. Otherwise, it defaults to the creator_id (student creating their own event).
        target_user_id = event_in.user_id if event_in.user_id else creator_id

        db_event = CalendarEvent(
            user_id=target_user_id,
            created_by=creator_id,
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
