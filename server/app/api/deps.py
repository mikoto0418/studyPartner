from typing import List
from fastapi import Depends, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.security import verify_token
from app.core.exceptions import AuthError, PermissionDenied
from app.services.user_service import UserService
from app.models.user import User

reusable_oauth2 = HTTPBearer(scheme_name="Bearer", auto_error=False)

async def get_current_user(
    db: AsyncSession = Depends(get_db),
    http_auth: HTTPAuthorizationCredentials = Security(reusable_oauth2)
) -> User:
    if not http_auth:
        raise AuthError("未登录，请先登录", code="UNAUTHORIZED")
    
    token = http_auth.credentials
    user_id_str = verify_token(token)
    if not user_id_str:
        raise AuthError("凭证已过期或无效", code="TOKEN_INVALID")

    from uuid import UUID
    user = await UserService.get_user(db, UUID(user_id_str))
    if not user:
        raise AuthError("用户不存在", code="USER_NOT_FOUND")
        
    if user.status == "disabled":
        raise AuthError("该账号已被禁用", code="USER_DISABLED")
        
    return user

async def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    if current_user.status != "active":
        raise AuthError("账号未激活或已被限制", code="USER_NOT_ACTIVE")
    return current_user

class RoleChecker:
    def __init__(self, allowed_roles: List[str]):
        self.allowed_roles = allowed_roles

    def __call__(self, current_user: User = Depends(get_current_active_user)) -> User:
        user_roles = [role.code for role in current_user.roles]
        # Check if user has any of the allowed roles
        if not any(role in user_roles for role in self.allowed_roles):
            raise PermissionDenied(f"权限不足，需要角色: {', '.join(self.allowed_roles)}")
        return current_user

# Predefined role checkers
require_admin = RoleChecker(["admin"])
require_teacher = RoleChecker(["teacher"])
require_staff = RoleChecker(["admin", "teacher"])
require_student = RoleChecker(["student"])
