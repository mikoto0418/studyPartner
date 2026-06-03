import io
import uuid
import asyncio
import hashlib
import logging
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Tuple
from uuid import UUID
from fastapi import UploadFile
from sqlalchemy import select, and_, desc, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.knowledge import FileModel, KnowledgeDocument, KnowledgeChunk
from app.models.user import User
from app.services.minio_service import MinioService
from app.services.vector_service import VectorService
from app.utils.parser import parse_document, chunk_text
from app.core.llm import llm_router, ChatMessage
from app.core.llm.providers.siliconflow import SiliconFlowProvider
from app.core.llm.providers.mock import MockProvider
from app.config import settings
from app.core.exceptions import NotFoundError, ValidationError

logger = logging.getLogger(__name__)

async def get_embedding(text: str) -> List[float]:
    """Generates vector embedding for text chunk using SiliconFlow or Mock fallback"""
    if settings.SILICONFLOW_API_KEY:
        provider = SiliconFlowProvider({
            "api_key": settings.SILICONFLOW_API_KEY,
            "base_url": settings.SILICONFLOW_BASE_URL
        })
        res = await provider.embedding(text, settings.SILICONFLOW_EMBEDDING_MODEL)
        # Handle if returns list
        if isinstance(res, list):
            return res[0].embedding
        return res.embedding
    else:
        provider = MockProvider()
        res = await provider.embedding(text, "mock-model")
        if isinstance(res, list):
            return res[0].embedding
        return res.embedding

class KnowledgeService:

    @staticmethod
    async def upload_file(
        db: AsyncSession,
        uploader_id: UUID,
        file: UploadFile,
        source: str = "upload"
    ) -> FileModel:
        """Saves uploader file to MinIO and writes tracking record to postgres database"""
        file_bytes = await file.read()
        file_size = len(file_bytes)
        
        # Calculate SHA256 hash for deduplication
        file_hash = hashlib.sha256(file_bytes).hexdigest()
        
        # Generate storage path: {source}/{uuid_hex}.{ext}
        ext = file.filename.split(".")[-1] if "." in file.filename else "bin"
        unique_name = f"{uuid.uuid4().hex}.{ext}"
        storage_path = f"{source}/{unique_name}"
        
        # Reset file cursor and upload to MinIO
        file_io = io.BytesIO(file_bytes)
        await asyncio.to_thread(
            MinioService.upload_file,
            storage_path,
            file_io,
            file_size,
            file.content_type or "application/octet-stream"
        )
        
        db_file = FileModel(
            id=uuid.uuid4(),
            uploader_id=uploader_id,
            original_name=file.filename,
            storage_path=storage_path,
            mime_type=file.content_type or "application/octet-stream",
            file_size=file_size,
            file_hash=file_hash,
            source=source
        )
        
        db.add(db_file)
        await db.commit()
        await db.refresh(db_file)
        return db_file

    @staticmethod
    async def create_document(
        db: AsyncSession,
        uploader_id: UUID,
        file_id: UUID,
        title: str,
        description: Optional[str] = None,
        category: Optional[str] = None,
        tags: Optional[List[str]] = None,
        visibility: str = "public"
    ) -> KnowledgeDocument:
        """Creates a knowledge base document in 'pending' status"""
        # Validate file
        stmt = select(FileModel).where(FileModel.id == file_id)
        res = await db.execute(stmt)
        db_file = res.scalars().first()
        if not db_file:
            raise NotFoundError("关联文件不存在")
            
        doc = KnowledgeDocument(
            id=uuid.uuid4(),
            file_id=file_id,
            uploader_id=uploader_id,
            title=title,
            description=description,
            category=category or "other",
            tags=tags or [],
            visibility=visibility,
            process_status="pending"
        )
        db.add(doc)
        await db.commit()
        await db.refresh(doc)
        return doc

    @staticmethod
    async def process_document(db: AsyncSession, document_id: UUID) -> KnowledgeDocument:
        """Runs the background text extraction, chunking, embedding, and vector upsert pipeline"""
        stmt = select(KnowledgeDocument).options(selectinload(KnowledgeDocument.file)).where(
            KnowledgeDocument.id == document_id
        )
        res = await db.execute(stmt)
        doc = res.scalars().first()
        if not doc:
            raise NotFoundError("知识库文档不存在")
            
        doc.process_status = "parsing"
        doc.process_error = None
        db.add(doc)
        await db.commit()
        
        try:
            # 1. Download file content from MinIO
            file_bytes = await asyncio.to_thread(
                MinioService.download_file,
                doc.file.storage_path
            )
            
            # 2. Parse text
            raw_text = parse_document(file_bytes, doc.file.original_name)
            if not raw_text.strip():
                raise ValidationError("文档内容解析为空，无有效可提取文本")
                
            # 3. Chunk text
            doc.process_status = "chunking"
            db.add(doc)
            await db.commit()
            
            chunks = chunk_text(raw_text, chunk_size=500, overlap=50)
            if not chunks:
                raise ValidationError("分片切割失败，未生成有效分片")
                
            # 4. Generate embeddings and index in Qdrant + Postgres
            doc.process_status = "embedding"
            db.add(doc)
            await db.commit()
            
            embedding_model = settings.SILICONFLOW_EMBEDDING_MODEL or "mock-model"
            indexed_chunks_count = 0
            
            for idx, text_content in enumerate(chunks):
                # Call embedding API
                vector = await get_embedding(text_content)
                
                # Generate unique chunk point id
                chunk_uuid = uuid.uuid4()
                
                # Save to Qdrant
                payload = {
                    "document_id": str(doc.id),
                    "chunk_index": idx,
                    "content": text_content,
                    "title": doc.title,
                    "uploader_id": str(doc.uploader_id),
                    "visibility": doc.visibility
                }
                
                success = await VectorService.upsert_chunk(
                    chunk_id=str(chunk_uuid),
                    vector=vector,
                    payload=payload
                )
                
                if success:
                    # Save chunk tracking to DB
                    db_chunk = KnowledgeChunk(
                        id=chunk_uuid,
                        document_id=doc.id,
                        chunk_index=idx,
                        content=text_content,
                        token_count=len(text_content) // 2, # simple token heuristic
                        embedding_model=embedding_model,
                        vector_id=str(chunk_uuid)
                    )
                    db.add(db_chunk)
                    indexed_chunks_count += 1
                    
            # 5. Generate document summary via LLM
            summary_text = None
            try:
                summary_prompt = (
                    "请阅读以下文档内容的提取文本，用简洁明了的中文为其生成一份【文档摘要】，"
                    "包含核心主题、主要结论和关键要点。限制在 300 字以内。"
                )
                # Take first 5000 characters to fit context limits comfortably
                doc_sample = raw_text[:5000]
                summary_messages = [
                    ChatMessage(role="system", content=summary_prompt),
                    ChatMessage(role="user", content=f"文档内容：\n\n{doc_sample}")
                ]
                summary_res = await llm_router.route(
                    task_type="document_summary",
                    messages=summary_messages,
                    user_id=doc.uploader_id,
                    stream=False
                )
                summary_text = summary_res.content
            except Exception as sum_err:
                logger.warning(f"Failed to generate summary for doc {doc.id}: {sum_err}")
                summary_text = doc.description or "文档处理完成，自动摘要生成失败。"
                
            # Update doc metadata
            doc.chunk_count = indexed_chunks_count
            doc.summary = summary_text
            doc.process_status = "completed"
            doc.processed_at = datetime.now(timezone.utc)
            db.add(doc)
            await db.commit()
            await db.refresh(doc)
            return doc
            
        except Exception as e:
            await db.rollback()
            logger.error(f"Error processing knowledge document {document_id}: {e}", exc_info=True)
            doc.process_status = "failed"
            doc.process_error = str(e)
            db.add(doc)
            await db.commit()
            raise e

    @staticmethod
    async def search_knowledge(
        db: AsyncSession,
        query_text: str,
        user_id: UUID,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """Semantic search in vector database returning matched chunks and parent document references"""
        vector = await get_embedding(query_text)
        
        # Search in Qdrant
        hits = await VectorService.search_similar_chunks(
            vector=vector,
            limit=limit,
            student_id=str(user_id)
        )
        
        results = []
        for hit in hits:
            doc_id_str = hit["payload"].get("document_id")
            if not doc_id_str:
                continue
                
            # Fetch document meta details from postgres
            doc_uuid = UUID(doc_id_str)
            stmt = select(KnowledgeDocument).where(KnowledgeDocument.id == doc_uuid)
            res = await db.execute(stmt)
            doc = res.scalars().first()
            if not doc or doc.deleted_at is not None:
                continue
                
            results.append({
                "chunk_id": hit["chunk_id"],
                "score": hit["score"],
                "content": hit["payload"].get("content"),
                "document_id": doc_id_str,
                "document_title": doc.title,
                "category": doc.category
            })
        return results

    @staticmethod
    async def delete_document(db: AsyncSession, document_id: UUID, user_id: UUID) -> bool:
        """Deletes a document from SQL registry, vector database, and object storage"""
        stmt = select(KnowledgeDocument).options(selectinload(KnowledgeDocument.file)).where(
            and_(KnowledgeDocument.id == document_id, KnowledgeDocument.deleted_at.is_(None))
        )
        res = await db.execute(stmt)
        doc = res.scalars().first()
        if not doc:
            raise NotFoundError("文档不存在或已被删除")
            
        # Verify ownership or permissions
        # (Uploader can delete, or admin can delete)
        # For simplicity, we authorize the uploader
        if doc.uploader_id != user_id:
            # Check if user is admin
            user_res = await db.execute(
                select(User).options(selectinload(User.roles)).where(User.id == user_id)
            )
            current_user = user_res.scalars().first()
            is_admin = current_user and any(r.code == "admin" for r in current_user.roles)
            if not is_admin:
                raise ValidationError("权限不足，只有上传者或管理员可以删除该文档")
                
        # 1. Soft delete document in Postgres
        doc.deleted_at = datetime.now(timezone.utc)
        db.add(doc)
        
        # 2. Delete points from Qdrant vector database
        await VectorService.delete_chunks_by_document(str(document_id))
        
        # 3. Remove physical file from MinIO
        await asyncio.to_thread(
            MinioService.delete_file,
            doc.file.storage_path
        )
        
        await db.commit()
        return True

    @staticmethod
    async def knowledge_qa(
        db: AsyncSession,
        query_text: str,
        user_id: UUID
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """RAG Q&A pipeline: similarity search, context assembly, and LLM routed query answering"""
        # 1. Similarity search
        chunks = await KnowledgeService.search_knowledge(db, query_text, user_id, limit=3)
        
        if not chunks:
            # Fallback to standard chat response if knowledge base is empty
            fallback_prompt = (
                "你是一个人工智能伴学助手。目前知识库中没有查找到与学生问题相关的参考资料。"
                "请根据你的通用知识回答学生的问题，并礼貌地提示他们如果需要针对特定文献的精准解答，可以先上传文档到知识库。"
            )
            messages = [
                ChatMessage(role="system", content=fallback_prompt),
                ChatMessage(role="user", content=query_text)
            ]
            llm_res = await llm_router.route(
                task_type="knowledge_qa",
                messages=messages,
                user_id=user_id,
                stream=False
            )
            return llm_res.content, []
            
        # 2. Assemble context
        context_str = ""
        citations = []
        for idx, c in enumerate(chunks):
            context_str += f"[{idx+1}] 《{c['document_title']}》:\n{c['content']}\n\n"
            citations.append({
                "source_index": idx + 1,
                "document_id": c["document_id"],
                "document_title": c["document_title"],
                "score": c["score"]
            })
            
        # 3. Call LLM
        qa_system_prompt = (
            "你是一个专业的知识库问答助手。请根据以下提供的参考资料，专业、准确且温和地回答学生的问题。"
            "如果参考资料中不包含解决问题所需的信息，请诚实告知，不要编造答案。\n\n"
            f"【参考资料】\n{context_str}"
            "请在回答中以 [1], [2] 的形式标注出你参考的文献来源。"
        )
        messages = [
            ChatMessage(role="system", content=qa_system_prompt),
            ChatMessage(role="user", content=query_text)
        ]
        
        llm_res = await llm_router.route(
            task_type="knowledge_qa",
            messages=messages,
            user_id=user_id,
            stream=False
        )
        return llm_res.content, citations
