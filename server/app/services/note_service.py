from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.note import Note
from app.schemas.note import NoteCreate, NoteUpdate
from app.core.exceptions import NotFoundError

class NoteService:
    @staticmethod
    async def get_note(db: AsyncSession, note_id: UUID, user_id: UUID) -> Optional[Note]:
        result = await db.execute(
            select(Note).where(
                and_(
                    Note.id == note_id,
                    Note.user_id == user_id,
                    Note.deleted_at.is_(None)
                )
            )
        )
        return result.scalars().first()

    @staticmethod
    async def list_notes(
        db: AsyncSession,
        user_id: UUID,
        category: Optional[str] = None
    ) -> List[Note]:
        query = select(Note).where(
            and_(
                Note.user_id == user_id,
                Note.deleted_at.is_(None)
            )
        )
        if category:
            query = query.where(Note.category == category)
            
        # Order by: pinned first (desc), then sort_order (asc), then created_at (desc)
        query = query.order_by(Note.is_pinned.desc(), Note.sort_order.asc(), Note.created_at.desc())
        
        result = await db.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def create_note(db: AsyncSession, user_id: UUID, note_in: NoteCreate) -> Note:
        db_note = Note(
            user_id=user_id,
            **note_in.model_dump()
        )
        db.add(db_note)
        await db.commit()
        await db.refresh(db_note)
        return db_note

    @classmethod
    async def update_note(
        cls, db: AsyncSession, note_id: UUID, user_id: UUID, note_in: NoteUpdate
    ) -> Note:
        db_note = await cls.get_note(db, note_id, user_id)
        if not db_note:
            raise NotFoundError("便签不存在")

        update_data = note_in.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_note, field, value)

        db_note.updated_at = datetime.now(timezone.utc)
        db.add(db_note)
        await db.commit()
        await db.refresh(db_note)
        return db_note

    @classmethod
    async def delete_note(cls, db: AsyncSession, note_id: UUID, user_id: UUID) -> bool:
        db_note = await cls.get_note(db, note_id, user_id)
        if not db_note:
            raise NotFoundError("便签不存在")
            
        db_note.deleted_at = datetime.now(timezone.utc)
        db.add(db_note)
        await db.commit()
        return True
