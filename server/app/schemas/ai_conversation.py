from datetime import datetime
from typing import Optional, List
from uuid import UUID
from pydantic import BaseModel, Field

class AIConversationCreate(BaseModel):
    title: Optional[str] = Field(None, description="对话标题（留空则自动生成）")
    conversation_type: str = Field("student_chat", alias="type", description="对话类型: student_chat, knowledge_qa, task_breakdown, plan_generate")

    class Config:
        populate_by_name = True

class AIConversationUpdate(BaseModel):
    title: str = Field(..., max_length=255, description="新标题")

class AIConversationOut(BaseModel):
    id: UUID
    user_id: UUID
    title: Optional[str]
    conversation_type: str = Field(..., alias="type")
    message_count: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
        populate_by_name = True

class ContextOptions(BaseModel):
    include_memory: bool = Field(True, description="是否注入 memory 上下文")
    include_todos: bool = Field(False, description="是否注入待办上下文")
    include_tasks: bool = Field(False, description="是否注入任务上下文")
    include_calendar: bool = Field(False, description="是否注入日历上下文")
    include_knowledge: bool = Field(False, description="是否检索知识库")
    knowledge_query: Optional[str] = Field(None, description="知识库检索查询")

class AIMessageCreate(BaseModel):
    content: str = Field(..., description="用户发送的消息正文")
    context_options: Optional[ContextOptions] = Field(default_factory=ContextOptions)

class AIMessageOut(BaseModel):
    id: UUID
    conversation_id: UUID
    role: str
    content: str
    token_count: Optional[int] = None
    model_name: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True
