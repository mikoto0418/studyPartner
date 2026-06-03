from typing import List, Optional
from datetime import date
from uuid import UUID
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.common import BaseResponse
from app.schemas.bilibili import HeatmapPointOut
from app.services.study_stat_service import HeatmapService
from app.api.deps import get_current_user
from app.models.user import User
from app.core.exceptions import PermissionDenied

router = APIRouter()

@router.get("/", response_model=BaseResponse[List[HeatmapPointOut]], summary="获取学习行为热力图数据")
async def get_heatmap_data(
    start_date: Optional[date] = Query(None, description="起始日期"),
    end_date: Optional[date] = Query(None, description="结束日期"),
    student_id: Optional[UUID] = Query(None, description="学生ID（老师/管理员查看他人时传入，学生默认为自己）"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    target_user_id = student_id or current_user.id
    
    # Permission verification
    user_roles = [r.code for r in current_user.roles]
    if "student" in user_roles and current_user.id != target_user_id:
        raise PermissionDenied("学生无权查看其他用户的学情行为热力图")
        
    points = await HeatmapService.get_heatmap_data(
        db=db,
        user_id=target_user_id,
        start_date=start_date,
        end_date=end_date
    )
    
    outs = [HeatmapPointOut(date=p["date"], count=p["count"]) for p in points]
    return BaseResponse.success(data=outs, message="获取成功")
