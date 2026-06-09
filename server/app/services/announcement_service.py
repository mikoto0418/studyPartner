from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID
from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.announcement import Announcement, AnnouncementReceiver, AnnouncementRead
from app.models.user import User, Role
from app.schemas.announcement import AnnouncementCreate, AnnouncementUpdate
from app.core.exceptions import NotFoundError
from app.services.notification_service import NotificationService

class AnnouncementService:
    @staticmethod
    async def _target_user_ids(db: AsyncSession, announcement: Announcement) -> List[UUID]:
        if announcement.target_type == "specific_users":
            rows = (await db.execute(
                select(AnnouncementReceiver.user_id).where(AnnouncementReceiver.announcement_id == announcement.id)
            )).scalars().all()
            return list(rows)

        stmt = select(User.id).where(User.deleted_at.is_(None), User.status == "active")
        if announcement.target_type == "all_students":
            stmt = stmt.join(User.roles).where(Role.code == "student")
        elif announcement.target_type == "all_teachers":
            stmt = stmt.join(User.roles).where(Role.code == "teacher")
        return list((await db.execute(stmt)).scalars().all())

    @staticmethod
    async def get_announcement(db: AsyncSession, announcement_id: UUID) -> Optional[Announcement]:
        result = await db.execute(
            select(Announcement).where(
                and_(
                    Announcement.id == announcement_id,
                    Announcement.deleted_at.is_(None)
                )
            )
        )
        return result.scalars().first()

    @staticmethod
    async def create_announcement(
        db: AsyncSession, creator_id: UUID, announcement_in: AnnouncementCreate
    ) -> Announcement:
        db_announcement = Announcement(
            creator_id=creator_id,
            title=announcement_in.title,
            content=announcement_in.content,
            status=announcement_in.status,
            target_type=announcement_in.target_type,
            is_pinned=announcement_in.is_pinned,
            publish_at=announcement_in.publish_at or datetime.now(timezone.utc),
            expire_at=announcement_in.expire_at
        )
        db.add(db_announcement)
        await db.flush()

        # If target_type is specific_users, add receivers
        if announcement_in.target_type == "specific_users" and announcement_in.receiver_ids:
            for r_id in announcement_in.receiver_ids:
                receiver = AnnouncementReceiver(announcement_id=db_announcement.id, user_id=r_id)
                db.add(receiver)

        await db.commit()
        await db.refresh(db_announcement)

        if db_announcement.status == "published":
            for user_id in await AnnouncementService._target_user_ids(db, db_announcement):
                if user_id == creator_id:
                    continue
                await NotificationService.create_notification(
                    db,
                    user_id=user_id,
                    title=f"公告：{db_announcement.title}",
                    content=db_announcement.content[:180],
                    notification_type="announcement",
                    link_url=None,
                )
        return db_announcement

    @staticmethod
    async def list_announcements_for_user(
        db: AsyncSession, user_id: UUID, role_codes: List[str]
    ) -> List[Announcement]:
        # User sees:
        # 1. target_type = 'all'
        # 2. target_type = 'all_students' if user is student
        # 3. target_type = 'all_teachers' if user is teacher
        # 4. target_type = 'specific_users' and user is in receivers
        conditions = [Announcement.target_type == "all"]
        
        if "student" in role_codes:
            conditions.append(Announcement.target_type == "all_students")
        if "teacher" in role_codes:
            conditions.append(Announcement.target_type == "all_teachers")
            
        # Specific receiver subquery
        specific_subquery = select(AnnouncementReceiver.announcement_id).where(AnnouncementReceiver.user_id == user_id)
        conditions.append(and_(Announcement.target_type == "specific_users", Announcement.id.in_(specific_subquery)))

        query = (
            select(Announcement)
            .where(
                and_(
                    Announcement.deleted_at.is_(None),
                    Announcement.status == "published",
                    Announcement.publish_at <= datetime.now(timezone.utc),
                    or_(*conditions)
                )
            )
            .order_by(Announcement.is_pinned.desc(), Announcement.publish_at.desc())
        )
        
        result = await db.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def mark_read(db: AsyncSession, announcement_id: UUID, user_id: UUID) -> bool:
        # Check if already read
        read_result = await db.execute(
            select(AnnouncementRead).where(
                and_(
                    AnnouncementRead.announcement_id == announcement_id,
                    AnnouncementRead.user_id == user_id
                )
            )
        )
        read_log = read_result.scalars().first()
        if not read_log:
            read_log = AnnouncementRead(
                announcement_id=announcement_id,
                user_id=user_id,
                read_at=datetime.now(timezone.utc)
            )
            db.add(read_log)
            await db.commit()
        return True
