import asyncio
import sys
import os
from uuid import UUID
from sqlalchemy import select

# Include server directory in search path
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "server"))

from app.core.database import SessionLocal
from app.models.user import User
from app.services.knowledge_service import KnowledgeService
from app.models.knowledge import KnowledgeDocument, KnowledgeChunk, FileModel

# Create custom dummy class simulating FastAPI's UploadFile
class DummyUploadFile:
    def __init__(self, filename: str, content: bytes, content_type: str = "text/plain"):
        self.filename = filename
        self._content = content
        self.content_type = content_type

    async def read(self) -> bytes:
        return self._content

async def test_rag_pipeline():
    print("==================================================")
    print("STARTING INTEGRATION TEST FOR KNOWLEDGE BASE & RAG")
    print("==================================================")
    
    async with SessionLocal() as db:
        # 1. Fetch default student
        res = await db.execute(select(User).where(User.username == "student"))
        student = res.scalars().first()
        if not student:
            print("[ERROR] Seeded student user 'student' not found! Make sure to run seeder first.")
            sys.exit(1)
        print(f"[OK] Found student user: {student.username} (ID: {student.id})")
        
        # Clean up database records for a fresh run
        from sqlalchemy import delete
        # Delete chunks, documents, and files
        stmt_docs = select(KnowledgeDocument).where(KnowledgeDocument.uploader_id == student.id)
        res_docs = await db.execute(stmt_docs)
        docs = res_docs.scalars().all()
        for doc in docs:
            # delete vectors from qdrant
            from app.services.vector_service import VectorService
            await VectorService.delete_chunks_by_document(str(doc.id))
            await db.execute(delete(KnowledgeChunk).where(KnowledgeChunk.document_id == doc.id))
            await db.execute(delete(KnowledgeDocument).where(KnowledgeDocument.id == doc.id))
            
        await db.execute(delete(FileModel).where(FileModel.uploader_id == student.id))
        await db.commit()
        
        # 2. Upload File
        file_content = (
            "Attention is all you need. The Transformer is a novel neural network architecture "
            "based on self-attention mechanisms. It outperforms recurrent and convolutional models "
            "in machine translation and other natural language processing tasks. "
            "By utilizing multi-head attention, the model learns dependencies between words in parallel, "
            "significantly reducing training times compared to LSTM or GRU models."
        ).encode("utf-8")
        
        dummy_file = DummyUploadFile(filename="transformer_paper.txt", content=file_content)
        print("[RUN] Uploading dummy document file to MinIO...")
        db_file = await KnowledgeService.upload_file(db, student.id, dummy_file, source="knowledge_base")
        print(f"[OK] File uploaded. ID: {db_file.id}, Path: {db_file.storage_path}")
        
        # 3. Create Knowledge Document
        print("[RUN] Creating knowledge document record...")
        doc = await KnowledgeService.create_document(
            db=db,
            uploader_id=student.id,
            file_id=db_file.id,
            title="Transformer 论文核心摘要",
            description="介绍自注意力机制与多头注意力的经典文献",
            category="deep_learning",
            tags=["AI", "Transformer", "Attention"],
            visibility="public"
        )
        print(f"[OK] Document created. ID: {doc.id}, Status: {doc.process_status}")
        
        # 4. Trigger Parsing/Chunking/Embedding Pipeline
        print("[RUN] Processing document chunks and generating embeddings with configured provider...")
        processed_doc = await KnowledgeService.process_document(db, doc.id)
        print(f"[OK] Document processing finished. Status: {processed_doc.process_status}")
        print(f"[OK] Chunks generated: {processed_doc.chunk_count}")
        print(f"[OK] Document summary: {processed_doc.summary}")
        
        # 5. Verify Postgres Chunks
        chunk_res = await db.execute(select(KnowledgeChunk).where(KnowledgeChunk.document_id == doc.id))
        db_chunks = chunk_res.scalars().all()
        print(f"[OK] Saved chunks count in DB: {len(db_chunks)}")
        assert len(db_chunks) > 0, "No chunks were saved to DB"
        
        # 6. Semantic Search Query
        query = "What is the core mechanism of the Transformer?"
        print(f"[RUN] Testing semantic search for query: '{query}'...")
        search_hits = await KnowledgeService.search_knowledge(db, query, student.id, limit=3)
        print(f"[OK] Search returned {len(search_hits)} results:")
        for idx, hit in enumerate(search_hits):
            print(f"  {idx+1}. Score: {hit['score']:.4f} | Document: {hit['document_title']} | Text: {hit['content'][:100]}...")
            
        assert len(search_hits) > 0, "Search did not return any hits"
        
        # 7. RAG Q&A
        print(f"[RUN] Testing RAG Q&A for query: '{query}'...")
        answer, citations = await KnowledgeService.knowledge_qa(db, query, student.id)
        print(f"[OK] AI Answer:\n{answer}")
        print(f"[OK] Citations referenced: {citations}")
        assert len(citations) > 0, "RAG answer should have citations"
        
    print("==================================================")
    print("KNOWLEDGE BASE & RAG TESTS PASSED SUCCESSFULLY!")
    print("==================================================")

if __name__ == "__main__":
    # Ensure correct working directory context
    os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    asyncio.run(test_rag_pipeline())
