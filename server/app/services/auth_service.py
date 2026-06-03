from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.user_service import UserService
from app.core.security import verify_password, create_access_token, create_refresh_token, verify_refresh_token, get_password_hash
from app.core.exceptions import AuthError, ValidationError
from app.schemas.auth import TokenOut, LoginRequest
from app.schemas.user import UserOut

class AuthService:
    @classmethod
    async def authenticate_user(cls, db: AsyncSession, login_in: LoginRequest) -> TokenOut:
        # User can login with either username or email
        user = None
        if "@" in login_in.username:
            user = await UserService.get_user_by_email(db, login_in.username)
        else:
            user = await UserService.get_user_by_username(db, login_in.username)

        if not user:
            raise AuthError("用户名或密码错误", code="INVALID_CREDENTIALS")

        if user.status == "disabled":
            raise AuthError("账号已被禁用，请联系管理员", code="USER_DISABLED")

        if not verify_password(login_in.password, user.password_hash):
            raise AuthError("用户名或密码错误", code="INVALID_CREDENTIALS")

        # Update last login time
        user.last_login_at = datetime.now(timezone.utc)
        db.add(user)
        await db.commit()

        # Generate tokens
        from app.config import settings
        access_token = create_access_token(subject=user.id)
        refresh_token = create_refresh_token(subject=user.id)

        user_out = UserOut.from_attributes(user)

        return TokenOut(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="Bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            user=user_out
        )

    @classmethod
    async def refresh_tokens(cls, db: AsyncSession, refresh_token: str) -> TokenOut:
        user_id_str = verify_refresh_token(refresh_token)
        if not user_id_str:
            raise AuthError("无效或过期的 Refresh Token", code="INVALID_REFRESH_TOKEN")

        from uuid import UUID
        user_id = UUID(user_id_str)
        user = await UserService.get_user(db, user_id)
        if not user:
            raise AuthError("用户不存在或已被删除", code="USER_NOT_FOUND")

        if user.status == "disabled":
            raise AuthError("账号已被禁用，请联系管理员", code="USER_DISABLED")

        # Generate new tokens
        from app.config import settings
        access_token = create_access_token(subject=user.id)
        new_refresh_token = create_refresh_token(subject=user.id)

        user_out = UserOut.from_attributes(user)

        return TokenOut(
            access_token=access_token,
            refresh_token=new_refresh_token,
            token_type="Bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            user=user_out
        )

    @staticmethod
    async def change_password(db: AsyncSession, user_id: str, old_password: str, new_password: str) -> bool:
        from uuid import UUID
        user = await UserService.get_user(db, UUID(user_id))
        if not user:
            raise ValidationError("用户不存在", code="USER_NOT_FOUND")

        if not verify_password(old_password, user.password_hash):
            raise ValidationError("原密码错误", code="INVALID_OLD_PASSWORD")

        user.password_hash = get_password_hash(new_password)
        user.updated_at = datetime.now(timezone.utc)
        db.add(user)
        await db.commit()
        return True
