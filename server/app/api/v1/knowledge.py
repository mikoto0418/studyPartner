from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, Body, Query, Path, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, desc, func

from app.core.database import get_db
from app.schemas.common import BaseResponse, PageData
from app.schemas.knowledge import (
    KnowledgeDocumentCreate, 
    KnowledgeDocumentOut, 
    RAGQueryReq, 
    RAGAnswerOut,
    CitationItem
)
from app.services.knowledge_service import KnowledgeService
from app.models.knowledge import KnowledgeDocument
from app.api.deps import get_current_user
from app.models.user import User
from app.core.exceptions import NotFoundError, ValidationError

router = APIRouter()

@router.post("/documents", response_model=BaseResponse[KnowledgeDocumentOut], summary="上传创建知识库文档")
async def create_document(
    doc_in: KnowledgeDocumentCreate = Body(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    doc = await KnowledgeService.create_document(
        db=db,
        uploader_id=current_user.id,
        file_id=doc_in.file_id,
        title=doc_in.title,
        description=doc_in.description,
        category=doc_in.category,
        tags=doc_in.tags,
        visibility=doc_in.visibility
    )
    
    # Dispatch Celery async task for background document parsing
    from app.tasks.celery_tasks import parse_document_task
    parse_document_task.delay(str(doc.id))
    
    return BaseResponse.success(
        data=KnowledgeDocumentOut.from_attributes(doc),
        message="文档关联成功，切片提取与向量化任务已提交 Celery 后台队列处理"
    )

@router.get("/documents", response_model=BaseResponse[PageData[KnowledgeDocumentOut]], summary="获取知识库文档列表")
async def list_documents(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页条数"),
    category: Optional[str] = Query(None, description="分类"),
    visibility: Optional[str] = Query(None, description="可见性: public, teachers_only, private"),
    keyword: Optional[str] = Query(None, description="关键字检索标题"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(KnowledgeDocument).where(KnowledgeDocument.deleted_at.is_(None))
    
    # Filter based on role permissions
    user_roles = [role.code for role in current_user.roles]
    if "student" in user_roles:
        # Students can see public docs OR their own private ones
        stmt = stmt.where(
            and_(
                KnowledgeDocument.deleted_at.is_(None),
                (KnowledgeDocument.visibility == "public") | (KnowledgeDocument.uploader_id == current_user.id)
            )
        )
    elif "teacher" in user_roles:
        # Teachers can see public, teachers_only OR their own
        stmt = stmt.where(
            and_(
                KnowledgeDocument.deleted_at.is_(None),
                (KnowledgeDocument.visibility.in_(["public", "teachers_only"])) | (KnowledgeDocument.uploader_id == current_user.id)
            )
        )
    # Admin can see everything
    
    if category:
        stmt = stmt.where(KnowledgeDocument.category == category)
    if visibility:
        stmt = stmt.where(KnowledgeDocument.visibility == visibility)
    if keyword:
        stmt = stmt.where(KnowledgeDocument.title.ilike(f"%{keyword}%"))
        
    stmt = stmt.order_by(desc(KnowledgeDocument.created_at))
    
    # Count
    count_stmt = select(func.count()).select_from(stmt.subquery())
    count_res = await db.execute(count_stmt)
    total = count_res.scalar() or 0
    
    # Limit
    stmt = stmt.offset((page - 1) * page_size).limit(page_size)
    res = await db.execute(stmt)
    items = list(res.scalars().all())
    
    outs = [KnowledgeDocumentOut.from_attributes(doc) for doc in items]
    page_data = PageData.create(items=outs, total=total, page=page, page_size=page_size)
    
    return BaseResponse.success(data=page_data, message="获取成功")

@router.get("/documents/{document_id}", response_model=BaseResponse[KnowledgeDocumentOut], summary="获取知识库文档详情")
async def get_document_details(
    document_id: UUID = Path(..., description="文档ID"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(KnowledgeDocument).where(
        and_(KnowledgeDocument.id == document_id, KnowledgeDocument.deleted_at.is_(None))
    )
    res = await db.execute(stmt)
    doc = res.scalars().first()
    if not doc:
        raise NotFoundError("文档不存在或已删除")
        
    return BaseResponse.success(data=KnowledgeDocumentOut.from_attributes(doc), message="获取成功")

@router.delete("/documents/{document_id}", response_model=BaseResponse[bool], summary="删除知识库文档")
async def delete_document(
    document_id: UUID = Path(..., description="文档ID"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    await KnowledgeService.delete_document(db, document_id, current_user.id)
    return BaseResponse.success(data=True, message="删除成功")

@router.post("/search", response_model=BaseResponse[List[dict]], summary="知识库语义段落搜索")
async def search_knowledge_chunks(
    req: RAGQueryReq = Body(...),
    limit: int = Query(5, ge=1, le=20, description="最大返回数量"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    results = await KnowledgeService.search_knowledge(
        db=db,
        query_text=req.query,
        user_id=current_user.id,
        limit=limit
    )
    return BaseResponse.success(data=results, message="搜索成功")

@router.post("/qa", response_model=BaseResponse[RAGAnswerOut], summary="知识库 RAG 增强问答")
async def knowledge_base_qa(
    req: RAGQueryReq = Body(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    answer, citations = await KnowledgeService.knowledge_qa(
        db=db,
        query_text=req.query,
        user_id=current_user.id
    )
    
    citation_outs = [
        CitationItem(
            source_index=c["source_index"],
            document_id=c["document_id"],
            document_title=c["document_title"],
            score=c["score"]
        )
        for c in citations
    ]
    
    data = RAGAnswerOut(
        answer=answer,
        citations=citation_outs
    )
    return BaseResponse.success(data=data, message="回答成功")
