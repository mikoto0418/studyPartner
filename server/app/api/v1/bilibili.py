from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Body, Query, Path
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.common import BaseResponse
from app.schemas.bilibili import (
    BilibiliMetaOut,
    BilibiliResourceCreate,
    BilibiliResourceOut,
    BilibiliWatchLogCreate,
    BilibiliWatchLogOut,
    BilibiliWatchStatOut,
)
from app.services.study_stat_service import BilibiliService
from app.api.deps import get_current_user
from app.models.user import User

router = APIRouter()


@router.get("/meta", response_model=BaseResponse[BilibiliMetaOut], summary="识别B站视频元信息")
async def get_bilibili_metadata(
    bvid: str = Query(..., description="BV号"),
    current_user: User = Depends(get_current_user),
):
    meta = await BilibiliService.fetch_resource_metadata(bvid)
    return BaseResponse.success(data=BilibiliMetaOut(**meta), message="识别成功")


@router.post("/", response_model=BaseResponse[BilibiliResourceOut], summary="添加B站视频资源")
async def add_bilibili_resource(
    res_in: BilibiliResourceCreate = Body(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    resource = await BilibiliService.add_resource(db, current_user.id, res_in)
    return BaseResponse.success(data=BilibiliResourceOut.model_validate(resource), message="添加成功")

@router.get("/", response_model=BaseResponse[List[BilibiliResourceOut]], summary="获取视频资源列表")
async def list_bilibili_resources(
    keyword: Optional[str] = Query(None, description="搜索关键词"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    items = await BilibiliService.list_resources(db, current_user.id, keyword)
    return BaseResponse.success(data=[BilibiliResourceOut.model_validate(i) for i in items], message="获取成功")

@router.delete("/{resource_id}", response_model=BaseResponse[bool], summary="软删除视频资源")
async def delete_bilibili_resource(
    resource_id: UUID = Path(..., description="视频资源ID"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    await BilibiliService.delete_resource(db, resource_id, current_user.id)
    return BaseResponse.success(data=True, message="删除成功")

@router.post("/log", response_model=BaseResponse[BilibiliWatchLogOut], summary="记录视频观看进度及心跳")
async def log_watch_event(
    event_in: BilibiliWatchLogCreate = Body(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    log = await BilibiliService.log_watch_event(db, current_user.id, event_in)
    return BaseResponse.success(data=BilibiliWatchLogOut.model_validate(log), message="进度记录成功")


@router.get("/stats", response_model=BaseResponse[List[BilibiliWatchStatOut]], summary="获取B站观看统计")
async def get_bilibili_watch_stats(
    resource_id: Optional[UUID] = Query(None, description="视频资源ID"),
    limit: int = Query(30, ge=1, le=100, description="返回记录数"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    stats = await BilibiliService.get_watch_stats(
        db=db,
        user_id=current_user.id,
        resource_id=resource_id,
        limit=limit,
    )
    return BaseResponse.success(data=[BilibiliWatchStatOut(**item) for item in stats], message="获取成功")
