from sqlalchemy import Column, String, Text, Integer, BigInteger, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.models.base import BaseModel

class FileModel(BaseModel):
    __tablename__ = "files"

    uploader_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    original_name = Column(String(255), nullable=False)
    storage_path = Column(String(512), nullable=False)
    mime_type = Column(String(128), nullable=False)
    file_size = Column(BigInteger, nullable=False)
    file_hash = Column(String(64), nullable=True, index=True)
    source = Column(String(32), default="upload", nullable=False, index=True)
    context_metadata = Column(JSONB, nullable=True)

    # Relationships
    uploader = relationship("User", backref="uploaded_files")

class KnowledgeDocument(BaseModel):
    __tablename__ = "knowledge_documents"

    file_id = Column(UUID(as_uuid=True), ForeignKey("files.id", ondelete="RESTRICT"), nullable=False)
    uploader_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    category = Column(String(64), nullable=True, index=True)
    tags = Column(JSONB, nullable=True)
    visibility = Column(String(20), default="public", nullable=False, index=True)
    process_status = Column(String(20), default="pending", nullable=False, index=True)
    process_error = Column(Text, nullable=True)
    summary = Column(Text, nullable=True)
    chunk_count = Column(Integer, default=0, nullable=True)
    processed_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    file = relationship("FileModel", backref="knowledge_documents")
    uploader = relationship("User", backref="knowledge_documents")

class KnowledgeChunk(BaseModel):
    __tablename__ = "knowledge_chunks"

    document_id = Column(UUID(as_uuid=True), ForeignKey("knowledge_documents.id", ondelete="CASCADE"), nullable=False, index=True)
    chunk_index = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    token_count = Column(Integer, nullable=True)
    embedding_model = Column(String(128), nullable=True)
    vector_id = Column(String(128), nullable=True, index=True)
    context_metadata = Column(JSONB, nullable=True)

    __table_args__ = (
        UniqueConstraint("document_id", "chunk_index", name="uq_knowledge_chunks_doc_index"),
    )

    # Relationships
    document = relationship("KnowledgeDocument", backref="chunks")
