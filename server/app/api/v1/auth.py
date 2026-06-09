from fastapi import APIRouter, Depends, Body
from sqlalchemy.ext.asyncio import AsyncSession
import random
from app.core.database import get_db
from app.schemas.common import BaseResponse
from app.schemas.auth import (
    LoginRequest, TokenOut, RefreshTokenRequest, ChangePasswordRequest,
    SendCodeRequest, RegisterRequest, ResetPasswordRequest
)
from app.schemas.user import UserOut, UserCreate
from app.services.auth_service import AuthService
from app.services.user_service import UserService
from app.services.email_service import EmailService
from app.core.redis import redis_client
from app.core.exceptions import ValidationError
from app.api.deps import get_current_user
from app.models.user import User

router = APIRouter()

@router.post("/login", response_model=BaseResponse[TokenOut], summary="用户登录")
async def login(
    login_in: LoginRequest,
    db: AsyncSession = Depends(get_db)
):
    token_data = await AuthService.authenticate_user(db, login_in)
    return BaseResponse.success(data=token_data, message="登录成功")

@router.post("/refresh", response_model=BaseResponse[TokenOut], summary="刷新Token")
async def refresh(
    refresh_in: RefreshTokenRequest,
    db: AsyncSession = Depends(get_db)
):
    token_data = await AuthService.refresh_tokens(db, refresh_in.refresh_token)
    return BaseResponse.success(data=token_data, message="Token刷新成功")

@router.post("/change-password", response_model=BaseResponse[bool], summary="修改密码")
async def change_password(
    change_in: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    await AuthService.change_password(
        db, 
        str(current_user.id), 
        change_in.old_password, 
        change_in.new_password
    )
    return BaseResponse.success(data=True, message="密码修改成功")

@router.get("/me", response_model=BaseResponse[UserOut], summary="获取当前登录用户信息")
async def get_me(current_user: User = Depends(get_current_user)):
    user_out = UserOut.model_validate(current_user)
    return BaseResponse.success(data=user_out, message="获取成功")

@router.post("/send-code", response_model=BaseResponse[bool], summary="发送邮箱验证码")
async def send_code(
    req: SendCodeRequest = Body(...),
    db: AsyncSession = Depends(get_db)
):
    user = await UserService.get_user_by_email(db, req.email)
    if req.action_type == "register":
        if user:
            raise ValidationError("该邮箱已被注册", code="EMAIL_EXISTS")
    elif req.action_type == "reset_password":
        if not user:
            raise ValidationError("该邮箱未注册", code="EMAIL_NOT_FOUND")
    else:
        raise ValidationError("无效的操作类型", code="INVALID_ACTION_TYPE")
    
    code = f"{random.randint(100000, 999999)}"
    redis_key = f"auth:code:{req.action_type}:{req.email}"

    await EmailService.send_verification_code(req.email, code)
    await redis_client.setex(redis_key, 300, code) # 5 minutes
    
    return BaseResponse.success(data=True, message="验证码已发送，请检查邮箱")

@router.post("/register", response_model=BaseResponse[UserOut], summary="自主注册")
async def register(
    req: RegisterRequest = Body(...),
    db: AsyncSession = Depends(get_db)
):
    if req.role not in ["student", "teacher"]:
        raise ValidationError("仅支持注册学生和教师账号", code="INVALID_ROLE")

    redis_key = f"auth:code:register:{req.email}"
    cached_code = await redis_client.get(redis_key)
    if not cached_code or cached_code != req.code:
        raise ValidationError("验证码错误或已过期", code="INVALID_CODE")
    
    user_in = UserCreate(
        username=req.username,
        email=req.email,
        password=req.password,
        role_codes=[req.role],
        nickname=None,
        status="active"
    )
    user = await UserService.create_user(db, user_in)
    await redis_client.delete(redis_key)
    
    return BaseResponse.success(data=UserOut.model_validate(user), message="注册成功")

@router.post("/reset-password", response_model=BaseResponse[bool], summary="重置密码")
async def reset_password(
    req: ResetPasswordRequest = Body(...),
    db: AsyncSession = Depends(get_db)
):
    redis_key = f"auth:code:reset_password:{req.email}"
    cached_code = await redis_client.get(redis_key)
    if not cached_code or cached_code != req.code:
        raise ValidationError("验证码错误或已过期", code="INVALID_CODE")
        
    user = await UserService.get_user_by_email(db, req.email)
    if not user:
        raise ValidationError("用户不存在", code="USER_NOT_FOUND")
        
    from app.core.security import get_password_hash
    from datetime import datetime, timezone
    user.password_hash = get_password_hash(req.new_password)
    user.updated_at = datetime.now(timezone.utc)
    db.add(user)
    await db.commit()
    
    await redis_client.delete(redis_key)
    
    return BaseResponse.success(data=True, message="密码重置成功")
