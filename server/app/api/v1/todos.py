from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, Query, Path, Body
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.schemas.common import BaseResponse
from app.schemas.todo import TodoOut, TodoCreate, TodoUpdate
from app.services.todo_service import TodoService
from app.api.deps import get_current_user
from app.models.user import User

router = APIRouter()

@router.get("/", response_model=BaseResponse[List[TodoOut]], summary="获取待办事项列表")
async def list_todos(
    status: Optional[str] = Query(None, description="状态: pending, completed, cancelled"),
    priority: Optional[str] = Query(None, description="优先级: low, medium, high, urgent"),
    category: Optional[str] = Query(None, description="分类"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    todos = await TodoService.list_todos(
        db, 
        user_id=current_user.id, 
        status=status, 
        priority=priority, 
        category=category
    )
    return BaseResponse.success(data=[TodoOut.model_validate(t) for t in todos], message="获取成功")

@router.post("/", response_model=BaseResponse[TodoOut], summary="创建待办事项")
async def create_todo(
    todo_in: TodoCreate = Body(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    todo = await TodoService.create_todo(db, user_id=current_user.id, todo_in=todo_in)
    return BaseResponse.success(data=TodoOut.model_validate(todo), message="创建成功")

@router.put("/{todo_id}", response_model=BaseResponse[TodoOut], summary="更新待办事项")
async def update_todo(
    todo_id: UUID = Path(..., description="待办事项ID"),
    todo_in: TodoUpdate = Body(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    todo = await TodoService.update_todo(
        db, 
        todo_id=todo_id, 
        user_id=current_user.id, 
        todo_in=todo_in
    )
    return BaseResponse.success(data=TodoOut.model_validate(todo), message="更新成功")

@router.delete("/{todo_id}", response_model=BaseResponse[bool], summary="删除待办事项")
async def delete_todo(
    todo_id: UUID = Path(..., description="待办事项ID"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    await TodoService.delete_todo(db, todo_id=todo_id, user_id=current_user.id)
    return BaseResponse.success(data=True, message="删除成功")
