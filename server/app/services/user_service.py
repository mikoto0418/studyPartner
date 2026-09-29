import re
from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID, uuid4
from sqlalchemy import select, and_, update, func, false, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.models.user import User, Role, StudentProfile, UserRole
from app.schemas.user import UserCreate, UserUpdate, StudentProfileUpdate, StudentAccountIn
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
            nickname=user_in.nickname,
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
    async def bulk_create_students(
        cls, db: AsyncSession, students: List[StudentAccountIn]
    ) -> tuple[List[dict], List[dict]]:
        """按名单批量开学生账号，返回 (created, skipped)。

        单条失败（重名、学号已被占用、学号太短）只记进 skipped 并给出原因，
        不中断整批 —— 一次导几十个人的时候，不该因为一行有问题就全部回滚。
        """
        created: List[dict] = []
        skipped: List[dict] = []
        seen: set = set()
        for item in students:
            student_no = (item.student_id or "").strip()
            if not student_no:
                skipped.append({"student_id": "", "reason": "学号为空"})
                continue
            if student_no in seen:
                skipped.append({"student_id": student_no, "reason": "名单里重复出现"})
                continue
            seen.add(student_no)

            username = (item.username or student_no).strip()
            password = (item.password or student_no).strip()
            if len(password) < 6:
                skipped.append({
                    "student_id": student_no,
                    "reason": "默认密码（学号）不足 6 位，请在名单里显式指定密码",
                })
                continue

            # 邮箱有唯一约束且必须是合法地址：从学号里剔掉非法字符，实在没有可用字符
            # 就退化成随机本地名，避免整条因为邮箱格式挂掉。域名不能用 .local /
            # .test / .example 这类保留域名，email-validator 会直接判为非法。
            local = re.sub(r"[^A-Za-z0-9._-]", "", student_no) or f"stu{uuid4().hex[:8]}"
            try:
                user = await cls.create_user(
                    db,
                    UserCreate(
                        username=username,
                        email=f"{local}@stu.example.com",
                        nickname=item.name,
                        password=password,
                        role_codes=["student"],
                    ),
                )
            except ValidationError as exc:
                skipped.append({"student_id": student_no, "reason": str(getattr(exc, "message", exc))})
                continue
            except Exception as exc:  # noqa: BLE001 - 单条异常不应拖垮整批
                skipped.append({"student_id": student_no, "reason": f"创建失败：{exc}"})
                continue

            # 学号不在 UserCreate 里，得单独落到学生档案上；否则之后按学号发卷、
            # 按学号搜索都找不到人（现有 create_user 建的档案学号是空的）。
            profile_res = await db.execute(
                select(StudentProfile).where(StudentProfile.user_id == user.id)
            )
            profile = profile_res.scalars().first()
            if profile:
                profile.student_id = student_no
                profile.grade = item.grade
                profile.major = item.major
                await db.commit()

            created.append({
                "student_id": student_no,
                "name": item.name,
                "username": username,
                "password": password,
                "user_id": str(user.id),
            })
        return created, skipped

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
    async def list_users(
        db: AsyncSession,
        role_code: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
        user_ids: Optional[List[UUID]] = None,
        keyword: Optional[str] = None,
        grade: Optional[str] = None,
        major: Optional[str] = None,
        status: Optional[str] = None,
    ):
        # Build query
        query = select(User).where(User.deleted_at.is_(None))
        if role_code:
            query = query.join(User.roles).where(Role.code == role_code)
        if user_ids is not None:
            query = query.where(User.id.in_(user_ids) if user_ids else false())
        if status:
            query = query.where(User.status == status)

        needs_profile_join = any([keyword, grade, major])
        if needs_profile_join:
            query = query.outerjoin(StudentProfile, StudentProfile.user_id == User.id)
        if keyword:
            pattern = f"%{keyword.strip()}%"
            query = query.where(or_(
                User.username.ilike(pattern),
                User.nickname.ilike(pattern),
                User.email.ilike(pattern),
                User.phone.ilike(pattern),
                StudentProfile.student_id.ilike(pattern),
                StudentProfile.grade.ilike(pattern),
                StudentProfile.major.ilike(pattern),
                StudentProfile.research_direction.ilike(pattern),
            ))
        if grade:
            query = query.where(StudentProfile.grade.ilike(f"%{grade.strip()}%"))
        if major:
            query = query.where(StudentProfile.major.ilike(f"%{major.strip()}%"))
        query = query.distinct()

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
