from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.todo import Todo
from app.schemas.todo import TodoCreate, TodoUpdate
from app.core.exceptions import NotFoundError

class TodoService:
    @staticmethod
    async def get_todo(db: AsyncSession, todo_id: UUID, user_id: UUID) -> Optional[Todo]:
        result = await db.execute(
            select(Todo).where(
                and_(
                    Todo.id == todo_id,
                    Todo.user_id == user_id,
                    Todo.deleted_at.is_(None)
                )
            )
        )
        return result.scalars().first()

    @staticmethod
    async def list_todos(
        db: AsyncSession,
        user_id: UUID,
        status: Optional[str] = None,
        priority: Optional[str] = None,
        category: Optional[str] = None
    ) -> List[Todo]:
        query = select(Todo).where(
            and_(
                Todo.user_id == user_id,
                Todo.deleted_at.is_(None)
            )
        )
        if status:
            query = query.where(Todo.status == status)
        if priority:
            query = query.where(Todo.priority == priority)
        if category:
            query = query.where(Todo.category == category)
            
        # Order by sort_order ascending, then created_at descending
        query = query.order_by(Todo.sort_order.asc(), Todo.created_at.desc())
        
        result = await db.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def create_todo(db: AsyncSession, user_id: UUID, todo_in: TodoCreate) -> Todo:
        db_todo = Todo(
            user_id=user_id,
            **todo_in.model_dump()
        )
        db.add(db_todo)
        await db.commit()
        await db.refresh(db_todo)
        return db_todo

    @classmethod
    async def update_todo(
        cls, db: AsyncSession, todo_id: UUID, user_id: UUID, todo_in: TodoUpdate
    ) -> Todo:
        db_todo = await cls.get_todo(db, todo_id, user_id)
        if not db_todo:
            raise NotFoundError("待办事项不存在")

        update_data = todo_in.model_dump(exclude_unset=True)
        
        # Auto set completed_at based on status changes
        if "status" in update_data:
            if update_data["status"] == "completed" and db_todo.status != "completed":
                db_todo.completed_at = datetime.now(timezone.utc)
            elif update_data["status"] != "completed" and db_todo.status == "completed":
                db_todo.completed_at = None

        for field, value in update_data.items():
            setattr(db_todo, field, value)

        db_todo.updated_at = datetime.now(timezone.utc)
        db.add(db_todo)
        await db.commit()
        await db.refresh(db_todo)
        return db_todo

    @classmethod
    async def delete_todo(cls, db: AsyncSession, todo_id: UUID, user_id: UUID) -> bool:
        db_todo = await cls.get_todo(db, todo_id, user_id)
        if not db_todo:
            raise NotFoundError("待办事项不存在")
            
        db_todo.deleted_at = datetime.now(timezone.utc)
        db.add(db_todo)
        await db.commit()
        return True
