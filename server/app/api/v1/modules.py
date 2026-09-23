from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_admin
from app.core.database import get_db
from app.core.exceptions import NotFoundError
from app.models.user import User
from app.schemas.common import BaseResponse
from app.schemas.module import ModuleOut, ModuleUpdate
from app.services.module_service import ModuleService

router = APIRouter()


@router.get("", response_model=BaseResponse[List[ModuleOut]], summary="获取当前用户可见功能模块")
async def get_my_modules(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    role = ModuleService._primary_role(current_user.role_codes)
    data = await ModuleService.list_for_role(db, role)
    return BaseResponse.success(data=[ModuleOut(**m) for m in data], message="获取成功")


@router.get("/all", response_model=BaseResponse[List[ModuleOut]], summary="管理员获取全部功能模块")
async def get_all_modules(
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    data = await ModuleService.list_all(db)
    return BaseResponse.success(data=[ModuleOut(**m) for m in data], message="获取成功")


@router.patch("/{code}", response_model=BaseResponse[ModuleOut], summary="管理员开关功能模块")
async def update_module(
    code: str,
    body: ModuleUpdate,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    try:
        data = await ModuleService.update_module(db, code, body.enabled, body.visible)
    except KeyError:
        raise NotFoundError("功能模块不存在")
    return BaseResponse.success(data=ModuleOut(**data), message="已更新")