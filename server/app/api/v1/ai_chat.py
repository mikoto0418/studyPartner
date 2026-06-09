from typing import List, Any, Dict
from uuid import UUID
from fastapi import APIRouter, Depends, Body, Query, Path
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.schemas.common import BaseResponse, PageData
from app.schemas.ai_conversation import (
    AIConversationCreate,
    AIConversationUpdate,
    AIConversationOut,
    AIMessageCreate,
    AIMessageOut
)
from app.services.ai_chat_service import AIChatService
from app.api.deps import get_current_user
from app.models.user import User

router = APIRouter()

@router.post("/conversations", response_model=BaseResponse[AIConversationOut], status_code=201, summary="创建新对话")
async def create_conversation(
    conv_in: AIConversationCreate = Body(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    conv = await AIChatService.create_conversation(
        db, user_id=current_user.id, title=conv_in.title, conversation_type=conv_in.conversation_type
    )
    return BaseResponse.success(
        data=AIConversationOut.model_validate(conv),
        message="对话创建成功"
    )

@router.get("/conversations", response_model=BaseResponse[PageData[AIConversationOut]], summary="获取当前用户的对话会话列表")
async def list_conversations(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    conversation_type: str = Query(None, alias="type"),
    keyword: str = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    items, total = await AIChatService.list_conversations(
        db, user_id=current_user.id, page=page, page_size=page_size,
        conversation_type=conversation_type, keyword=keyword
    )
    page_data = PageData.create(
        items=[AIConversationOut.model_validate(item) for item in items],
        total=total,
        page=page,
        page_size=page_size
    )
    return BaseResponse.success(data=page_data, message="获取成功")

@router.patch("/conversations/{conversation_id}", response_model=BaseResponse[AIConversationOut], summary="更新对话标题")
async def update_conversation_title(
    conversation_id: UUID = Path(...),
    conv_in: AIConversationUpdate = Body(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    conv = await AIChatService.update_conversation_title(
        db, conversation_id=conversation_id, user_id=current_user.id, title=conv_in.title
    )
    return BaseResponse.success(data=AIConversationOut.model_validate(conv), message="标题已更新")

@router.delete("/conversations/{conversation_id}", response_model=BaseResponse[bool], summary="删除对话")
async def delete_conversation(
    conversation_id: UUID = Path(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    await AIChatService.delete_conversation(db, conversation_id=conversation_id, user_id=current_user.id)
    return BaseResponse.success(data=True, message="对话已删除")

@router.get("/conversations/{conversation_id}/messages", response_model=BaseResponse[PageData[AIMessageOut]], summary="获取对话历史消息")
async def list_messages(
    conversation_id: UUID = Path(...),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    items, total = await AIChatService.list_messages(
        db, conversation_id=conversation_id, user_id=current_user.id, page=page, page_size=page_size
    )
    page_data = PageData.create(
        items=[AIMessageOut.model_validate(item) for item in items],
        total=total,
        page=page,
        page_size=page_size
    )
    return BaseResponse.success(data=page_data, message="获取成功")

@router.post("/conversations/{conversation_id}/messages", summary="发送消息（流式）")
async def send_message(
    conversation_id: UUID = Path(...),
    message_in: AIMessageCreate = Body(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    sse_generator = await AIChatService.send_message_stream(
        db, conversation_id=conversation_id, user_id=current_user.id,
        content=message_in.content, options=message_in.context_options
    )
    return StreamingResponse(sse_generator, media_type="text/event-stream")
