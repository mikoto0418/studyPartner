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

router = APIRouter()

@router.get("/", response_model=BaseResponse[PageData[UserOut]], summary="获取用户列表")
async def list_users(
    role_code: str = Query(None, description="按角色筛选"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页大小"),
    current_user: User = Depends(require_staff),
    db: AsyncSession = Depends(get_db)
):
    items, total = await UserService.list_users(db, role_code=role_code, page=page, page_size=page_size)
    page_data = PageData.create(
        items=[UserOut.from_attributes(item) for item in items],
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
    return BaseResponse.success(data=UserOut.from_attributes(user), message="创建成功")

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
    return BaseResponse.success(data=UserOut.from_attributes(updated), message="更新成功")

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
    # Only the student themselves or staff (teacher/admin) can update the profile
    if "admin" not in current_user.role_codes and "teacher" not in current_user.role_codes and current_user.id != user_id:
        raise PermissionDenied("无权修改该学生档案")

    profile = await UserService.update_student_profile(db, user_id, profile_in)
    return BaseResponse.success(data=StudentProfileOut.from_attributes(profile), message="更新成功")
