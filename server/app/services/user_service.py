from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID
from sqlalchemy import select, and_, update, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.models.user import User, Role, StudentProfile, UserRole
from app.schemas.user import UserCreate, UserUpdate, StudentProfileUpdate
from app.core.security import get_password_hash
from app.core.exceptions import ValidationError, NotFoundError

class UserService:
    @staticmethod
    async def get_user(db: AsyncSession, user_id: UUID) -> Optional[User]:
        result = await db.execute(
            select(User)
            .options(selectinload(User.roles), selectinload(User.student_profile))
            .where(and_(User.id == user_id, User.deleted_at.is_(None)))
        )
        return result.scalars().first()

    @staticmethod
    async def get_user_by_username(db: AsyncSession, username: str) -> Optional[User]:
        result = await db.execute(
            select(User)
            .options(selectinload(User.roles), selectinload(User.student_profile))
            .where(and_(User.username == username, User.deleted_at.is_(None)))
        )
        return result.scalars().first()

    @staticmethod
    async def get_user_by_email(db: AsyncSession, email: str) -> Optional[User]:
        result = await db.execute(
            select(User)
            .options(selectinload(User.roles), selectinload(User.student_profile))
            .where(and_(User.email == email, User.deleted_at.is_(None)))
        )
        return result.scalars().first()

    @staticmethod
    async def get_role_by_code(db: AsyncSession, code: str) -> Optional[Role]:
        result = await db.execute(select(Role).where(Role.code == code))
        return result.scalars().first()

    @classmethod
    async def create_user(cls, db: AsyncSession, user_in: UserCreate) -> User:
        # Check if username or email already exists
        existing_username = await cls.get_user_by_username(db, user_in.username)
        if existing_username:
            raise ValidationError("用户名已存在", code="USERNAME_EXISTS")
            
        existing_email = await cls.get_user_by_email(db, user_in.email)
        if existing_email:
            raise ValidationError("邮箱已存在", code="EMAIL_EXISTS")

        # Create user
        db_user = User(
            username=user_in.username,
            email=user_in.email,
            nickname=user_in.nickname or user_in.username,
            phone=user_in.phone,
            status=user_in.status,
            password_hash=get_password_hash(user_in.password),
        )
        db.add(db_user)
        await db.flush() # Generate ID

        # Link roles
        for r_code in user_in.role_codes:
            role = await cls.get_role_by_code(db, r_code)
            if not role:
                # If role doesn't exist during dev, create it
                role = Role(code=r_code, name=r_code.capitalize(), description=f"{r_code} role")
                db.add(role)
                await db.flush()
            
            user_role = UserRole(user_id=db_user.id, role_id=role.id)
            db.add(user_role)

        # If it's a student, automatically create student profile
        if "student" in user_in.role_codes:
            student_profile = StudentProfile(user_id=db_user.id)
            db.add(student_profile)

        await db.commit()
        # Reload to load relationship attributes
        return await cls.get_user(db, db_user.id)

    @classmethod
    async def update_user(cls, db: AsyncSession, db_user: User, user_in: UserUpdate) -> User:
        if user_in.email and user_in.email != db_user.email:
            existing = await cls.get_user_by_email(db, user_in.email)
            if existing:
                raise ValidationError("邮箱已存在", code="EMAIL_EXISTS")
            db_user.email = user_in.email

        if user_in.nickname is not None:
            db_user.nickname = user_in.nickname
        if user_in.phone is not None:
            db_user.phone = user_in.phone
        if user_in.avatar_url is not None:
            db_user.avatar_url = user_in.avatar_url
        if user_in.status is not None:
            db_user.status = user_in.status
        if user_in.password is not None:
            db_user.password_hash = get_password_hash(user_in.password)

        db_user.updated_at = datetime.now(timezone.utc)
        db.add(db_user)
        await db.commit()
        return await cls.get_user(db, db_user.id)

    @classmethod
    async def update_student_profile(
        cls, db: AsyncSession, user_id: UUID, profile_in: StudentProfileUpdate
    ) -> StudentProfile:
        result = await db.execute(select(StudentProfile).where(StudentProfile.user_id == user_id))
        profile = result.scalars().first()
        if not profile:
            profile = StudentProfile(user_id=user_id)
            db.add(profile)
            await db.flush()

        # Update fields
        for field, value in profile_in.model_dump(exclude_unset=True).items():
            setattr(profile, field, value)

        profile.updated_at = datetime.now(timezone.utc)
        db.add(profile)
        await db.commit()
        await db.refresh(profile)
        return profile

    @classmethod
    async def delete_user(cls, db: AsyncSession, user_id: UUID) -> bool:
        db_user = await cls.get_user(db, user_id)
        if not db_user:
            raise NotFoundError("用户不存在")
        
        # Soft delete
        db_user.deleted_at = datetime.now(timezone.utc)
        db.add(db_user)
        await db.commit()
        return True

    @staticmethod
    async def list_users(db: AsyncSession, role_code: Optional[str] = None, page: int = 1, page_size: int = 20):
        # Build query
        query = select(User).where(User.deleted_at.is_(None))
        if role_code:
            query = query.join(User.roles).where(Role.code == role_code)

        # Count total
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await db.execute(count_query)
        total = total_result.scalar() or 0

        # Paginate
        query = query.options(selectinload(User.roles), selectinload(User.student_profile))
        query = query.offset((page - 1) * page_size).limit(page_size)
        result = await db.execute(query)
        items = result.scalars().all()

        return items, total
