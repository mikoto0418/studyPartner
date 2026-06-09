from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Body, Depends, Path, Query
from sqlalchemy import and_, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.exceptions import NotFoundError
from app.models.knowledge import FileModel, KnowledgeDocument
from app.models.task import Task, TaskAssignee
from app.models.user import User
from app.schemas.common import BaseResponse, PageData
from app.schemas.knowledge import (
    CitationItem,
    KnowledgeDocumentCreate,
    KnowledgeDocumentOut,
    KnowledgeDocumentUpdate,
    RAGAnswerOut,
    RAGQueryReq,
    TeacherAssignedFileOut,
)
from app.services.knowledge_service import KnowledgeService

router = APIRouter()


@router.post("/documents", response_model=BaseResponse[KnowledgeDocumentOut], summary="Create knowledge document")
async def create_document(
    doc_in: KnowledgeDocumentCreate = Body(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    doc = await KnowledgeService.create_document(
        db=db,
        uploader_id=current_user.id,
        file_id=doc_in.file_id,
        title=doc_in.title,
        description=doc_in.description,
        category=doc_in.category,
        tags=doc_in.tags,
        visibility=doc_in.visibility,
    )

    from app.tasks.celery_tasks import parse_document_task

    parse_document_task.delay(str(doc.id))
    return BaseResponse.success(
        data=KnowledgeDocumentOut.model_validate(doc),
        message="Document created and parsing task queued",
    )


@router.get("/documents", response_model=BaseResponse[PageData[KnowledgeDocumentOut]], summary="List knowledge documents")
async def list_documents(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    category: Optional[str] = Query(None),
    visibility: Optional[str] = Query(None),
    keyword: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(KnowledgeDocument).where(KnowledgeDocument.deleted_at.is_(None))

    user_roles = [role.code for role in current_user.roles]
    if "student" in user_roles:
        stmt = stmt.where(
            (KnowledgeDocument.visibility == "public") | (KnowledgeDocument.uploader_id == current_user.id)
        )
    elif "teacher" in user_roles:
        stmt = stmt.where(
            (KnowledgeDocument.visibility.in_(["public", "teachers_only"]))
            | (KnowledgeDocument.uploader_id == current_user.id)
        )

    if category:
        stmt = stmt.where(KnowledgeDocument.category == category)
    if visibility:
        stmt = stmt.where(KnowledgeDocument.visibility == visibility)
    if keyword:
        stmt = stmt.where(KnowledgeDocument.title.ilike(f"%{keyword}%"))

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await db.execute(count_stmt)).scalar() or 0

    stmt = stmt.order_by(desc(KnowledgeDocument.created_at)).offset((page - 1) * page_size).limit(page_size)
    res = await db.execute(stmt)
    docs = [KnowledgeDocumentOut.model_validate(doc) for doc in res.scalars().all()]
    page_data = PageData.create(items=docs, total=total, page=page, page_size=page_size)
    return BaseResponse.success(data=page_data, message="OK")


@router.get("/teacher-files", response_model=BaseResponse[List[TeacherAssignedFileOut]], summary="List teacher assigned files")
async def list_teacher_assigned_files(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    task_stmt = (
        select(Task, TaskAssignee.status)
        .join(TaskAssignee, Task.id == TaskAssignee.task_id)
        .where(
            and_(
                TaskAssignee.user_id == current_user.id,
                Task.deleted_at.is_(None),
                Task.attachment_ids.is_not(None),
            )
        )
        .order_by(desc(Task.created_at))
    )
    task_rows = (await db.execute(task_stmt)).all()

    file_ids: set[UUID] = set()
    task_file_map: list[tuple[Task, str, UUID]] = []
    for task, status in task_rows:
        for raw_id in task.attachment_ids or []:
            try:
                file_id = raw_id if isinstance(raw_id, UUID) else UUID(str(raw_id))
            except (ValueError, TypeError):
                continue
            file_ids.add(file_id)
            task_file_map.append((task, status, file_id))

    if not file_ids:
        return BaseResponse.success(data=[], message="OK")

    file_res = await db.execute(select(FileModel).where(FileModel.id.in_(file_ids)))
    files_by_id = {item.id: item for item in file_res.scalars().all()}

    items: list[TeacherAssignedFileOut] = []
    for task, status, file_id in task_file_map:
        db_file = files_by_id.get(file_id)
        if not db_file:
            continue
        items.append(
            TeacherAssignedFileOut(
                file=db_file,
                task_id=task.id,
                task_title=task.title,
                task_description=task.description,
                due_date=task.due_date,
                priority=task.priority,
                status=status,
            )
        )

    return BaseResponse.success(data=items, message="OK")


@router.get("/documents/{document_id}", response_model=BaseResponse[KnowledgeDocumentOut], summary="Get knowledge document")
async def get_document_details(
    document_id: UUID = Path(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    doc = await KnowledgeService.get_document_for_user(db, document_id, current_user)
    return BaseResponse.success(data=KnowledgeDocumentOut.model_validate(doc), message="OK")


@router.patch("/documents/{document_id}", response_model=BaseResponse[KnowledgeDocumentOut], summary="Update knowledge document")
async def update_document_metadata(
    document_id: UUID = Path(...),
    doc_in: KnowledgeDocumentUpdate = Body(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    doc = await KnowledgeService.update_document(
        db=db,
        document_id=document_id,
        user_id=current_user.id,
        title=doc_in.title,
        description=doc_in.description,
        category=doc_in.category,
        tags=doc_in.tags,
        visibility=doc_in.visibility,
    )
    return BaseResponse.success(data=KnowledgeDocumentOut.model_validate(doc), message="Updated")


@router.delete("/documents/{document_id}", response_model=BaseResponse[bool], summary="Delete knowledge document")
async def delete_document(
    document_id: UUID = Path(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await KnowledgeService.delete_document(db, document_id, current_user.id)
    return BaseResponse.success(data=True, message="Deleted")


@router.post("/search", response_model=BaseResponse[List[dict]], summary="Search knowledge chunks")
async def search_knowledge_chunks(
    req: RAGQueryReq = Body(...),
    limit: int = Query(5, ge=1, le=20),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    results = await KnowledgeService.search_knowledge(
        db=db,
        query_text=req.query,
        user_id=current_user.id,
        limit=limit,
    )
    return BaseResponse.success(data=results, message="OK")


@router.post("/qa", response_model=BaseResponse[RAGAnswerOut], summary="Knowledge base QA")
async def knowledge_base_qa(
    req: RAGQueryReq = Body(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    answer, citations = await KnowledgeService.knowledge_qa(
        db=db,
        query_text=req.query,
        user_id=current_user.id,
    )
    citation_outs = [
        CitationItem(
            source_index=c["source_index"],
            document_id=c["document_id"],
            document_title=c["document_title"],
            score=c["score"],
        )
        for c in citations
    ]
    return BaseResponse.success(data=RAGAnswerOut(answer=answer, citations=citation_outs), message="OK")
