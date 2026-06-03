from uuid import UUID
from fastapi import APIRouter, Depends, UploadFile, File, Form, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.common import BaseResponse
from app.schemas.knowledge import FileOut
from app.services.knowledge_service import KnowledgeService
from app.services.minio_service import MinioService
from app.api.deps import get_current_user
from app.models.user import User

router = APIRouter()

@router.post("/upload", response_model=BaseResponse[FileOut], summary="上传文件")
async def upload_file(
    file: UploadFile = File(...),
    source: str = Query("upload", description="文件来源/模块分类"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    db_file = await KnowledgeService.upload_file(
        db=db,
        uploader_id=current_user.id,
        file=file,
        source=source
    )
    return BaseResponse.success(data=FileOut.from_attributes(db_file), message="上传成功")

@router.get("/download", summary="获取文件下载直链或跳转地址")
async def get_download_url(
    path: str = Query(..., description="文件在 MinIO 中的存储路径"),
    current_user: User = Depends(get_current_user)
):
    url = MinioService.get_download_url(path)
    return BaseResponse.success(data={"url": url}, message="获取成功")
