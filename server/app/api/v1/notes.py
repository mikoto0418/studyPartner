from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, Query, Path, Body
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.schemas.common import BaseResponse
from app.schemas.note import NoteOut, NoteCreate, NoteUpdate
from app.services.note_service import NoteService
from app.api.deps import get_current_user
from app.models.user import User

router = APIRouter()

@router.get("/", response_model=BaseResponse[List[NoteOut]], summary="获取便签列表")
async def list_notes(
    category: Optional[str] = Query(None, description="分类"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    notes = await NoteService.list_notes(
        db, 
        user_id=current_user.id, 
        category=category
    )
    return BaseResponse.success(data=[NoteOut.model_validate(n) for n in notes], message="获取成功")

@router.post("/", response_model=BaseResponse[NoteOut], summary="创建便签")
async def create_note(
    note_in: NoteCreate = Body(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    note = await NoteService.create_note(db, user_id=current_user.id, note_in=note_in)
    return BaseResponse.success(data=NoteOut.model_validate(note), message="创建成功")

@router.put("/{note_id}", response_model=BaseResponse[NoteOut], summary="更新便签")
async def update_note(
    note_id: UUID = Path(..., description="便签ID"),
    note_in: NoteUpdate = Body(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    note = await NoteService.update_note(
        db, 
        note_id=note_id, 
        user_id=current_user.id, 
        note_in=note_in
    )
    return BaseResponse.success(data=NoteOut.model_validate(note), message="更新成功")

@router.delete("/{note_id}", response_model=BaseResponse[bool], summary="删除便签")
async def delete_note(
    note_id: UUID = Path(..., description="便签ID"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    await NoteService.delete_note(db, note_id=note_id, user_id=current_user.id)
    return BaseResponse.success(data=True, message="删除成功")
