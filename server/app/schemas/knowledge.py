from datetime import datetime
from typing import Optional, List, Any
from uuid import UUID
from pydantic import BaseModel, Field

class FileOut(BaseModel):
    id: UUID
    uploader_id: UUID
    original_name: str
    storage_path: str
    mime_type: str
    file_size: int
    source: str
    created_at: datetime

    class Config:
        from_attributes = True

class KnowledgeDocumentBase(BaseModel):
    title: str = Field(..., max_length=255, description="文档标题")
    description: Optional[str] = Field(None, description="文档详情/描述")
    category: Optional[str] = Field("other", description="分类")
    tags: Optional[List[str]] = Field(None, description="标签列表")
    visibility: str = Field("public", description="可见性: public, teachers_only, private")

class KnowledgeDocumentCreate(KnowledgeDocumentBase):
    file_id: UUID = Field(..., description="关联上传的文件ID")

class KnowledgeDocumentUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=255, description="Document title")
    description: Optional[str] = Field(None, description="Document description")
    category: Optional[str] = Field(None, description="Folder/category")
    tags: Optional[List[str]] = Field(None, description="Tag list")
    visibility: Optional[str] = Field(None, description="public, teachers_only, private")

class KnowledgeDocumentOut(KnowledgeDocumentBase):
    id: UUID
    file_id: UUID
    uploader_id: UUID
    process_status: str
    chunk_count: int
    summary: Optional[str] = None
    process_error: Optional[str] = None
    processed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class RAGQueryReq(BaseModel):
    query: str = Field(..., min_length=1, description="提问/检索关键字")

class CitationItem(BaseModel):
    source_index: int
    document_id: str
    document_title: str
    score: float

class RAGAnswerOut(BaseModel):
    answer: str
    citations: List[CitationItem] = []

class TeacherAssignedFileOut(BaseModel):
    file: FileOut
    task_id: UUID
    task_title: str
    task_description: Optional[str] = None
    due_date: Optional[datetime] = None
    priority: Optional[str] = None
    status: Optional[str] = None
