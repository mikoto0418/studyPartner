import logging
from typing import List, Dict, Any, Optional
from qdrant_client import QdrantClient
from qdrant_client.http import models as rest
from qdrant_client.http.models import Distance, VectorParams, PointStruct
from app.config import settings

logger = logging.getLogger(__name__)

class VectorService:
    _client: Optional[QdrantClient] = None

    @classmethod
    def get_client(cls) -> QdrantClient:
        if cls._client is None:
            cls._client = QdrantClient(
                host=settings.QDRANT_HOST,
                port=settings.QDRANT_PORT
            )
            cls._ensure_collection_exists()
        return cls._client

    @classmethod
    def _ensure_collection_exists(cls):
        try:
            client = cls._client
            # Check if collection exists
            collections_res = client.get_collections()
            exist = False
            for col in collections_res.collections:
                if col.name == settings.QDRANT_COLLECTION:
                    exist = True
                    break
            
            if not exist:
                client.create_collection(
                    collection_name=settings.QDRANT_COLLECTION,
                    vectors_config=VectorParams(size=1024, distance=Distance.COSINE),
                )
                logger.info(f"Successfully created Qdrant collection: {settings.QDRANT_COLLECTION}")
        except Exception as e:
            logger.error(f"Failed to ensure Qdrant collection exists: {e}", exc_info=True)

    @classmethod
    async def upsert_chunk(
        cls,
        chunk_id: str,
        vector: List[float],
        payload: Dict[str, Any]
    ) -> bool:
        """Upsert a single text chunk vector embedding into Qdrant"""
        try:
            client = cls.get_client()
            client.upsert(
                collection_name=settings.QDRANT_COLLECTION,
                points=[
                    PointStruct(
                        id=chunk_id,
                        vector=vector,
                        payload=payload
                    )
                ]
            )
            return True
        except Exception as e:
            logger.error(f"Qdrant upsert_chunk failed for {chunk_id}: {e}", exc_info=True)
            return False

    @classmethod
    async def search_similar_chunks(
        cls,
        vector: List[float],
        limit: int = 5,
        student_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Searches similar vectors in Qdrant with optional student visibility filter"""
        try:
            client = cls.get_client()
            
            query_filter = None
            if student_id:
                # Filter so student can only read public docs or their private docs
                # For simplicity, we can filter documents by accessibility payload
                query_filter = rest.Filter(
                    should=[
                        rest.FieldCondition(
                            key="uploader_id",
                            match=rest.MatchValue(value=student_id)
                        ),
                        rest.FieldCondition(
                            key="visibility",
                            match=rest.MatchValue(value="public")
                        )
                    ]
                )

            search_result = client.query_points(
                collection_name=settings.QDRANT_COLLECTION,
                query=vector,
                query_filter=query_filter,
                limit=limit
            )
            
            results = []
            for hit in search_result.points:
                results.append({
                    "chunk_id": hit.id,
                    "score": hit.score,
                    "payload": hit.payload
                })
            return results
        except Exception as e:
            logger.error(f"Qdrant search_similar_chunks failed: {e}", exc_info=True)
            return []

    @classmethod
    async def delete_chunks_by_document(cls, document_id: str) -> bool:
        """Removes all vectors belonging to a specific document"""
        try:
            client = cls.get_client()
            client.delete(
                collection_name=settings.QDRANT_COLLECTION,
                points_selector=rest.FilterSelector(
                    filter=rest.Filter(
                        must=[
                            rest.FieldCondition(
                                key="document_id",
                                match=rest.MatchValue(value=document_id)
                            )
                        ]
                    )
                )
            )
            logger.info(f"Successfully deleted Qdrant vector chunks for document {document_id}")
            return True
        except Exception as e:
            logger.error(f"Qdrant delete_chunks_by_document failed for {document_id}: {e}", exc_info=True)
            return False
