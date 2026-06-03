from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID
from sqlalchemy import select, and_, update
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.notification import Notification
from app.core.exceptions import NotFoundError

class NotificationService:
    @staticmethod
    async def create_notification(
        db: AsyncSession,
        user_id: UUID,
        title: str,
        content: str,
        notification_type: str = "system",
        link_url: Optional[str] = None
    ) -> Notification:
        db_notification = Notification(
            user_id=user_id,
            title=title,
            content=content,
            notification_type=notification_type,
            link_url=link_url
        )
        db.add(db_notification)
        await db.commit()
        await db.refresh(db_notification)

        # Send WebSocket real-time push notification
        from app.core.websocket_manager import manager
        try:
            payload = {
                "type": "notification",
                "data": {
                    "id": str(db_notification.id),
                    "title": db_notification.title,
                    "content": db_notification.content,
                    "notification_type": db_notification.notification_type,
                    "link_url": db_notification.link_url,
                    "created_at": db_notification.created_at.isoformat() if db_notification.created_at else None
                }
            }
            await manager.send_personal_message(payload, str(user_id))
        except Exception:
            pass

        return db_notification

    @staticmethod
    async def list_notifications(
        db: AsyncSession,
        user_id: UUID,
        unread_only: bool = False
    ) -> List[Notification]:
        query = select(Notification).where(Notification.user_id == user_id)
        if unread_only:
            query = query.where(Notification.read_at.is_(None))
            
        query = query.order_by(Notification.created_at.desc())
        
        result = await db.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def mark_read(db: AsyncSession, notification_id: UUID, user_id: UUID) -> Notification:
        result = await db.execute(
            select(Notification).where(
                and_(Notification.id == notification_id, Notification.user_id == user_id)
            )
        )
        notification = result.scalars().first()
        if not notification:
            raise NotFoundError("通知不存在")

        if not notification.read_at:
            notification.read_at = datetime.now(timezone.utc)
            db.add(notification)
            await db.commit()
            await db.refresh(notification)
        return notification

    @staticmethod
    async def mark_all_read(db: AsyncSession, user_id: UUID) -> bool:
        await db.execute(
            update(Notification)
            .where(and_(Notification.user_id == user_id, Notification.read_at.is_(None)))
            .values(read_at=datetime.now(timezone.utc))
        )
        await db.commit()
        return True
