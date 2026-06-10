from fastapi import APIRouter, Depends, Query, Path, Body
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from app.core.database import get_db
from app.schemas.common import BaseResponse, PageData
from app.schemas.user import UserOut, UserCreate, UserUpdate, StudentProfileOut, StudentProfileUpdate
from app.services.user_service import UserService
from app.api.deps import get_current_user, require_admin, require_staff
from app.models.user import User
from app.core.exceptions import PermissionDenied
from app.services.access_control import AccessControlService

router = APIRouter()

@router.get("/", response_model=BaseResponse[PageData[UserOut]], summary="获取用户列表")
async def list_users(
    role_code: str = Query(None, description="按角色筛选"),
    keyword: str = Query(None, description="按姓名、账号、邮箱、学号、年级、专业检索"),
    grade: str = Query(None, description="按年级筛选"),
    major: str = Query(None, description="按专业筛选"),
    status: str = Query(None, description="按用户状态筛选"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页大小"),
    current_user: User = Depends(require_staff),
    db: AsyncSession = Depends(get_db)
):
    allowed_user_ids = None
    if "admin" not in current_user.role_codes:
        if role_code and role_code != "student":
            raise PermissionDenied("老师只能查看自己关联的学生列表")
        allowed_user_ids = await AccessControlService.accessible_student_ids(db, current_user)
        role_code = "student"

    items, total = await UserService.list_users(
        db,
        role_code=role_code,
        page=page,
        page_size=page_size,
        user_ids=allowed_user_ids,
        keyword=keyword,
        grade=grade,
        major=major,
        status=status,
    )
    page_data = PageData.create(
        items=[UserOut.model_validate(item) for item in items],
        total=total,
        page=page,
        page_size=page_size
    )
    return BaseResponse.success(data=page_data, message="获取成功")

@router.post("/", response_model=BaseResponse[UserOut], summary="创建新用户")
async def create_user(
    user_in: UserCreate,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    user = await UserService.create_user(db, user_in)
    return BaseResponse.success(data=UserOut.model_validate(user), message="创建成功")

@router.put("/{user_id}", response_model=BaseResponse[UserOut], summary="更新用户")
async def update_user(
    user_id: UUID = Path(..., description="用户ID"),
    user_in: UserUpdate = Body(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Standard user can only update themselves. Admin can update anyone.
    if "admin" not in current_user.role_codes and current_user.id != user_id:
        raise PermissionDenied("无权更新其他用户信息")

    from app.services.user_service import UserService
    target_user = await UserService.get_user(db, user_id)
    if not target_user:
        from app.core.exceptions import NotFoundError
        raise NotFoundError("用户不存在")

    # If non-admin is trying to change status or roles (handled via UserUpdate), deny it.
    if "admin" not in current_user.role_codes:
        user_in.status = None # Reset so they can't self-promote or toggle status

    updated = await UserService.update_user(db, target_user, user_in)
    return BaseResponse.success(data=UserOut.model_validate(updated), message="更新成功")

@router.delete("/{user_id}", response_model=BaseResponse[bool], summary="删除用户")
async def delete_user(
    user_id: UUID = Path(..., description="用户ID"),
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    await UserService.delete_user(db, user_id)
    return BaseResponse.success(data=True, message="删除成功")

@router.put("/{user_id}/student-profile", response_model=BaseResponse[StudentProfileOut], summary="更新学生档案")
async def update_student_profile(
    user_id: UUID = Path(..., description="用户ID"),
    profile_in: StudentProfileUpdate = Body(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    if "admin" not in current_user.role_codes and current_user.id != user_id:
        await AccessControlService.ensure_can_access_student(db, current_user, user_id)

    profile = await UserService.update_student_profile(db, user_id, profile_in)
    return BaseResponse.success(data=StudentProfileOut.model_validate(profile), message="更新成功")
