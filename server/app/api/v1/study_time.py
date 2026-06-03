from fastapi import APIRouter, Depends, Body
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.common import BaseResponse
from app.schemas.bilibili import StudyTimeHeartbeatReq
from app.services.study_stat_service import StudyTimeService
from app.api.deps import get_current_user
from app.models.user import User

router = APIRouter()

@router.post("/heartbeat", response_model=BaseResponse[bool], summary="上报在线学习时间心跳")
async def report_heartbeat(
    heartbeat_in: StudyTimeHeartbeatReq = Body(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    await StudyTimeService.heartbeat(
        db=db,
        user_id=current_user.id,
        heartbeat_in=heartbeat_in
    )
    await db.commit()
    return BaseResponse.success(data=True, message="心跳接收成功")
