from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Body, Depends, Path, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.exceptions import PermissionDenied, ValidationError
from app.models.user import User
from app.schemas.common import BaseResponse, PageData
from app.schemas.memory_wiki import (
    MemoryEventOut,
    MemoryGraphOut,
    MemoryGraphEdge,
    MemoryGraphNode,
    MemoryLintIssue,
    MemoryLintOut,
    MemoryLinkCreate,
    MemoryLinkOut,
    MemoryPageCreate,
    MemoryPageDetailOut,
    MemoryPageOut,
    MemoryPageUpdate,
    MemoryReviewTaskOut,
    MemorySearchHit,
    MemorySearchReq,
    MemorySourceCreate,
    MemorySourceOut,
    MemoryWikiStatsOut,
)
from app.services.access_control import AccessControlService
from app.services.memory_wiki_service import MemoryWikiService

router = APIRouter()


async def resolve_target_student_id(
    db: AsyncSession,
    current_user: User,
    requested_student_id: Optional[UUID],
) -> UUID:
    if "student" in current_user.role_codes:
        if requested_student_id and requested_student_id != current_user.id:
            raise PermissionDenied("学生只能访问自己的 Memory Wiki")
        return current_user.id

    if not any(r in current_user.role_codes for r in ["teacher", "admin"]):
        raise PermissionDenied("无权访问 Memory Wiki")

    if not requested_student_id:
        raise ValidationError("老师/管理员访问时必须指定 student_id", code="STUDENT_ID_REQUIRED")

    await AccessControlService.ensure_can_access_student(db, current_user, requested_student_id)
    return requested_student_id


def _page_to_out(page) -> MemoryPageOut:
    return MemoryPageOut(
        id=page.id,
        user_id=page.user_id,
        slug=page.slug,
        page_type=page.page_type,
        title=page.title,
        summary=page.summary,
        body=page.body,
        category=page.category,
        tags=page.tags,
        confidence=page.confidence,
        status=page.status,
        version=page.version,
        source_review_id=page.source_review_id,
        last_reviewed_at=page.last_reviewed_at,
        expires_at=page.expires_at,
        created_at=page.created_at,
        updated_at=page.updated_at,
    )


@router.get("/stats", response_model=BaseResponse[MemoryWikiStatsOut], summary="Memory Wiki 统计")
async def get_memory_wiki_stats(
    student_id: Optional[UUID] = Query(None, description="学生ID（老师/管理员必填）"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    target_id = await resolve_target_student_id(db, current_user, student_id)
    stats = await MemoryWikiService.get_stats(db, target_id)
    return BaseResponse.success(data=MemoryWikiStatsOut(**stats), message="获取成功")


@router.get("", response_model=BaseResponse[PageData[MemoryPageOut]], summary="获取 Memory Wiki 页面列表")
async def list_memory_pages(
    student_id: Optional[UUID] = Query(None, description="学生ID（老师/管理员必填）"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    page_type: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    status: str = Query("active", description="active/draft/archived/deleted"),
    keyword: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    target_id = await resolve_target_student_id(db, current_user, student_id)
    pages, total = await MemoryWikiService.list_pages(
        db, target_id, page=page, page_size=page_size,
        page_type=page_type, category=category, status=status, keyword=keyword,
    )
    page_data = PageData.create(items=[_page_to_out(p) for p in pages], total=total, page=page, page_size=page_size)
    return BaseResponse.success(data=page_data, message="获取成功")


@router.get("/graph", response_model=BaseResponse[MemoryGraphOut], summary="Memory Wiki 图谱")
async def get_memory_graph(
    student_id: Optional[UUID] = Query(None, description="学生ID（老师/管理员必填）"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    target_id = await resolve_target_student_id(db, current_user, student_id)
    pages, links = await MemoryWikiService.get_graph(db, target_id)
    nodes = [
        MemoryGraphNode(
            id=p.id, title=p.title, page_type=p.page_type,
            category=p.category, confidence=p.confidence, status=p.status,
        )
        for p in pages
    ]
    edges = [
        MemoryGraphEdge(id=l.id, source=l.from_page_id, target=l.to_page_id, relation=l.relation, strength=l.strength)
        for l in links
    ]
    return BaseResponse.success(data=MemoryGraphOut(nodes=nodes, edges=edges), message="获取成功")


@router.get("/events", response_model=BaseResponse[PageData[MemoryEventOut]], summary="Memory Wiki 审计日志")
async def list_memory_events(
    student_id: Optional[UUID] = Query(None, description="学生ID（老师/管理员必填）"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    target_id = await resolve_target_student_id(db, current_user, student_id)
    events, total = await MemoryWikiService.list_events(db, target_id, page=page, page_size=page_size)
    page_data = PageData.create(items=[MemoryEventOut.model_validate(e) for e in events], total=total, page=page, page_size=page_size)
    return BaseResponse.success(data=page_data, message="获取成功")


@router.get("/review-tasks", response_model=BaseResponse[PageData[MemoryReviewTaskOut]], summary="Memory 人工确认任务")
async def list_review_tasks(
    student_id: Optional[UUID] = Query(None, description="学生ID（老师/管理员必填）"),
    status: str = Query("pending"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    target_id = await resolve_target_student_id(db, current_user, student_id)
    tasks, total = await MemoryWikiService.list_review_tasks(db, target_id, status=status, page=page, page_size=page_size)
    page_data = PageData.create(items=[MemoryReviewTaskOut.model_validate(t) for t in tasks], total=total, page=page, page_size=page_size)
    return BaseResponse.success(data=page_data, message="获取成功")


@router.post("/review-tasks/{task_id}/approve", response_model=BaseResponse[MemoryReviewTaskOut], summary="批准记忆变更")
async def approve_review_task(
    task_id: UUID = Path(...),
    reason: Optional[str] = Body(None, embed=True),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    task = await MemoryWikiService.handle_review_task(
        db, current_user.id, task_id, approve=True, reason=reason, operator="student",
    )
    return BaseResponse.success(data=MemoryReviewTaskOut.model_validate(task), message="已批准")


@router.post("/review-tasks/{task_id}/reject", response_model=BaseResponse[MemoryReviewTaskOut], summary="拒绝记忆变更")
async def reject_review_task(
    task_id: UUID = Path(...),
    reason: Optional[str] = Body(None, embed=True),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    task = await MemoryWikiService.handle_review_task(
        db, current_user.id, task_id, approve=False, reason=reason, operator="student",
    )
    return BaseResponse.success(data=MemoryReviewTaskOut.model_validate(task), message="已拒绝")


@router.post("/lint", response_model=BaseResponse[MemoryLintOut], summary="运行 Memory Wiki 健康检查")
async def run_memory_lint(
    student_id: Optional[UUID] = Query(None, description="学生ID（老师/管理员必填）"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    target_id = await resolve_target_student_id(db, current_user, student_id)
    issues = await MemoryWikiService.run_lint(db, target_id)
    stats = await MemoryWikiService.get_stats(db, target_id)
    data = MemoryLintOut(
        issues=[MemoryLintIssue(**issue) for issue in issues],
        checked_pages=stats["active_pages"],
    )
    return BaseResponse.success(data=data, message="检查完成")


@router.post("/search", response_model=BaseResponse[List[MemorySearchHit]], summary="搜索 Memory Wiki")
async def search_memory_pages(
    req: MemorySearchReq = Body(...),
    student_id: Optional[UUID] = Query(None, description="学生ID（老师/管理员必填）"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    target_id = await resolve_target_student_id(db, current_user, student_id)
    hits = await MemoryWikiService.search_pages(
        db, target_id, query=req.query, top_k=req.top_k,
        page_type=req.page_type, category=req.category, status=req.status,
    )
    data = [MemorySearchHit(page=_page_to_out(p), score=score) for p, score in hits]
    return BaseResponse.success(data=data, message="搜索成功")


@router.post("/pages", response_model=BaseResponse[MemoryPageOut], summary="创建 Memory Wiki 页面")
async def create_memory_page(
    data: MemoryPageCreate = Body(...),
    student_id: Optional[UUID] = Query(None, description="学生ID（老师/管理员必填）"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    target_id = await resolve_target_student_id(db, current_user, student_id)
    operator = "admin" if "admin" in current_user.role_codes else ("teacher" if "teacher" in current_user.role_codes else "student")
    page = await MemoryWikiService.create_page(db, target_id, data.model_dump(), operator=operator)
    return BaseResponse.success(data=_page_to_out(page), message="创建成功")


@router.get("/pages/{page_id}", response_model=BaseResponse[MemoryPageDetailOut], summary="获取 Memory Wiki 页面详情")
async def get_memory_page(
    page_id: UUID = Path(...),
    student_id: Optional[UUID] = Query(None, description="学生ID（老师/管理员必填）"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    target_id = await resolve_target_student_id(db, current_user, student_id)
    page = await MemoryWikiService.get_page(db, target_id, page_id, load_detail=True)
    out = MemoryPageDetailOut(
        **_page_to_out(page).model_dump(),
        sources=[
            {
                "id": s.id,
                "source_type": s.source_type,
                "source_id": s.source_id,
                "occurred_at": s.occurred_at,
                "snippet": s.snippet,
                "confidence": s.confidence,
                "meta": s.meta,
                "created_at": s.created_at,
            }
            for s in page.sources
        ],
        outbound_links=[
            {
                "id": l.id,
                "to_page_id": l.to_page_id,
                "relation": l.relation,
                "strength": l.strength,
                "target_title": l.to_page.title if l.to_page else None,
            }
            for l in page.outbound_links
        ],
        inbound_links=[
            {
                "id": l.id,
                "from_page_id": l.from_page_id,
                "relation": l.relation,
                "strength": l.strength,
                "source_title": l.from_page.title if l.from_page else None,
            }
            for l in page.inbound_links
        ],
    )
    return BaseResponse.success(data=out, message="获取成功")


@router.patch("/pages/{page_id}", response_model=BaseResponse[MemoryPageOut], summary="更新 Memory Wiki 页面")
async def update_memory_page(
    page_id: UUID = Path(...),
    data: MemoryPageUpdate = Body(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    page = await MemoryWikiService.update_page(
        db, current_user.id, page_id,
        data={k: v for k, v in data.model_dump(exclude_unset=True).items()},
        operator="student",
    )
    return BaseResponse.success(data=_page_to_out(page), message="更新成功")


@router.post("/pages/{page_id}/archive", response_model=BaseResponse[MemoryPageOut], summary="归档 Memory Wiki 页面")
async def archive_memory_page(
    page_id: UUID = Path(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    page = await MemoryWikiService.change_page_status(
        db, current_user.id, page_id, "archived", operator="student", reason="手动归档",
    )
    return BaseResponse.success(data=_page_to_out(page), message="已归档")


@router.post("/pages/{page_id}/delete", response_model=BaseResponse[MemoryPageOut], summary="删除 Memory Wiki 页面")
async def delete_memory_page(
    page_id: UUID = Path(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    page = await MemoryWikiService.change_page_status(
        db, current_user.id, page_id, "deleted", operator="student", reason="手动删除",
    )
    return BaseResponse.success(data=_page_to_out(page), message="已删除")


@router.get("/pages/{page_id}/sources", response_model=BaseResponse[List[MemorySourceOut]], summary="获取记忆页证据")
async def list_page_sources(
    page_id: UUID = Path(...),
    student_id: Optional[UUID] = Query(None, description="学生ID（老师/管理员必填）"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    target_id = await resolve_target_student_id(db, current_user, student_id)
    sources = await MemoryWikiService.list_sources(db, target_id, page_id)
    return BaseResponse.success(data=[MemorySourceOut.model_validate(s) for s in sources], message="获取成功")


@router.post("/pages/{page_id}/sources", response_model=BaseResponse[MemorySourceOut], summary="新增记忆证据")
async def add_page_source(
    page_id: UUID = Path(...),
    data: MemorySourceCreate = Body(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    source = await MemoryWikiService.add_source(db, current_user.id, page_id, data.model_dump())
    return BaseResponse.success(data=MemorySourceOut.model_validate(source), message="新增成功")


@router.get("/pages/{page_id}/links", response_model=BaseResponse[List[MemoryLinkOut]], summary="获取记忆页链接")
async def list_page_links(
    page_id: UUID = Path(...),
    student_id: Optional[UUID] = Query(None, description="学生ID（老师/管理员必填）"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    target_id = await resolve_target_student_id(db, current_user, student_id)
    outbound, inbound = await MemoryWikiService.list_links(db, target_id, page_id)
    return BaseResponse.success(data=[MemoryLinkOut.model_validate(l) for l in outbound + inbound], message="获取成功")


@router.post("/pages/{page_id}/links", response_model=BaseResponse[MemoryLinkOut], summary="新增记忆关联")
async def add_page_link(
    page_id: UUID = Path(...),
    data: MemoryLinkCreate = Body(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    link = await MemoryWikiService.add_link(db, current_user.id, page_id, data.model_dump())
    return BaseResponse.success(data=MemoryLinkOut.model_validate(link), message="新增成功")