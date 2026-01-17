
import os
from typing import Any
from uuid import UUID

from qdrant_client import QdrantClient
from qdrant_client.http import models as qdrant_models
from qdrant_client.http.exceptions import UnexpectedResponse

from app.core.config import settings
from app.core.exceptions import VectorStoreError
from app.core.logging import get_logger
from app.models.documents import DocumentChunk, RetrievedDocument

logger = get_logger(__name__)


class VectorStore:
    
    def __init__(
        self,
        collection_name: str | None = None,
        embedding_dimension: int | None = None,
    ) -> None:
        self.collection_name = collection_name or settings.qdrant_collection
        self.embedding_dimension = embedding_dimension or settings.embedding_dimension
        self._initialized = False
        
        # Initialize client based on configuration
        if settings.qdrant_url:
            # Cloud/remote deployment
            self.client = QdrantClient(
                url=settings.qdrant_url,
                api_key=settings.qdrant_api_key,
            )
            logger.info("Connected to Qdrant cloud", url=settings.qdrant_url)
        else:
            # Local/embedded deployment
            path = settings.qdrant_path
            os.makedirs(path, exist_ok=True)
            self.client = QdrantClient(path=path)
            logger.info("Using local Qdrant storage", path=path)
    
    def initialize(self) -> None:
        if self._initialized:
            return
            
        try:
            collections = self.client.get_collections().collections
            exists = any(c.name == self.collection_name for c in collections)
            
            if not exists:
                logger.info(
                    "Creating vector collection",
                    collection=self.collection_name,
                    dimension=self.embedding_dimension,
                )
                
                self.client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=qdrant_models.VectorParams(
                        size=self.embedding_dimension,
                        distance=qdrant_models.Distance.COSINE,
                    ),
                )
                
                # Create payload indexes for filtering
                self._create_indexes()
                logger.info("Collection created successfully")
            else:
                logger.info("Collection already exists", collection=self.collection_name)
            
            self._initialized = True
                
        except Exception as e:
            logger.error("Failed to initialize vector store", error=str(e))
            raise VectorStoreError(operation="initialize", reason=str(e))
    
    async def initialize_async(self) -> None:
        self.initialize()
    
    def _create_indexes(self) -> None:
        indexes = [
            ("document_type", qdrant_models.PayloadSchemaType.KEYWORD),
            ("document_id", qdrant_models.PayloadSchemaType.KEYWORD),
            ("client_name", qdrant_models.PayloadSchemaType.KEYWORD),
            ("practice_area", qdrant_models.PayloadSchemaType.KEYWORD),
        ]
        
        for field_name, field_type in indexes:
            try:
                self.client.create_payload_index(
                    collection_name=self.collection_name,
                    field_name=field_name,
                    field_schema=field_type,
                )
            except Exception:
                logger.debug(f"Index may already exist: {field_name}")
    
    def add_chunks(
        self,
        chunks: list[DocumentChunk],
        embeddings: list[list[float]],
    ) -> int:
        if not self._initialized:
            self.initialize()
            
        if len(chunks) != len(embeddings):
            raise VectorStoreError(
                operation="add_chunks",
                reason=f"Mismatch: {len(chunks)} chunks vs {len(embeddings)} embeddings",
            )
        
        if not chunks:
            return 0
        
        try:
            points = [
                qdrant_models.PointStruct(
                    id=str(chunk.chunk_id),
                    vector=embedding,
                    payload={
                        **chunk.to_vector_payload(),
                        "content": chunk.content,
                    },
                )
                for chunk, embedding in zip(chunks, embeddings)
            ]
            
            self.client.upsert(
                collection_name=self.collection_name,
                points=points,
            )
            
            logger.info(
                "Added chunks to vector store",
                count=len(chunks),
                document_id=str(chunks[0].document_id) if chunks else None,
            )
            
            return len(chunks)
            
        except Exception as e:
            logger.error("Failed to add chunks", error=str(e))
            raise VectorStoreError(operation="add_chunks", reason=str(e))
    
    async def add_chunks_async(
        self,
        chunks: list[DocumentChunk],
        embeddings: list[list[float]],
    ) -> int:
        return self.add_chunks(chunks, embeddings)
    
    def search(
        self,
        query_embedding: list[float],
        top_k: int = 10,
        filter_dict: dict[str, Any] | None = None,
        score_threshold: float | None = None,
    ) -> list[RetrievedDocument]:
        if not self._initialized:
            self.initialize()
            
        try:
            # Build filter conditions
            query_filter = None
            if filter_dict:
                conditions = []
                for field, values in filter_dict.items():
                    if isinstance(values, list):
                        if values:  # Only add if list is not empty
                            conditions.append(
                                qdrant_models.FieldCondition(
                                    key=field,
                                    match=qdrant_models.MatchAny(any=values),
                                )
                            )
                    else:
                        conditions.append(
                            qdrant_models.FieldCondition(
                                key=field,
                                match=qdrant_models.MatchValue(value=values),
                            )
                        )
                
                if conditions:
                    query_filter = qdrant_models.Filter(must=conditions)
            
            # Execute search
            results = self.client.search(
                collection_name=self.collection_name,
                query_vector=query_embedding,
                limit=top_k,
                query_filter=query_filter,
                score_threshold=score_threshold or settings.retrieval_min_score,
                with_payload=True,
            )
            
            # Convert to RetrievedDocument
            documents = []
            for rank, hit in enumerate(results):
                payload = hit.payload or {}
                doc = RetrievedDocument.from_search_result(
                    content=payload.get("content", ""),
                    score=hit.score,
                    rank=rank,
                    payload=payload,
                )
                documents.append(doc)
            
            logger.debug(
                "Vector search completed",
                results=len(documents),
                top_score=documents[0].score if documents else 0,
            )
            
            return documents
            
        except Exception as e:
            logger.error("Vector search failed", error=str(e))
            raise VectorStoreError(operation="search", reason=str(e))
    
    async def search_async(
        self,
        query_embedding: list[float],
        top_k: int = 10,
        filter_dict: dict[str, Any] | None = None,
        score_threshold: float | None = None,
    ) -> list[RetrievedDocument]:
        return self.search(query_embedding, top_k, filter_dict, score_threshold)
    
    def delete_document(self, document_id: UUID) -> int:
        if not self._initialized:
            self.initialize()
            
        try:
            count_result = self.client.count(
                collection_name=self.collection_name,
                count_filter=qdrant_models.Filter(
                    must=[
                        qdrant_models.FieldCondition(
                            key="document_id",
                            match=qdrant_models.MatchValue(value=str(document_id)),
                        )
                    ]
                ),
            )
            
            self.client.delete(
                collection_name=self.collection_name,
                points_selector=qdrant_models.FilterSelector(
                    filter=qdrant_models.Filter(
                        must=[
                            qdrant_models.FieldCondition(
                                key="document_id",
                                match=qdrant_models.MatchValue(value=str(document_id)),
                            )
                        ]
                    )
                ),
            )
            
            logger.info(
                "Deleted document chunks",
                document_id=str(document_id),
                count=count_result.count,
            )
            
            return count_result.count
            
        except Exception as e:
            logger.error("Failed to delete document", error=str(e))
            raise VectorStoreError(operation="delete_document", reason=str(e))
    
    def get_collection_stats(self) -> dict[str, Any]:
        if not self._initialized:
            self.initialize()
            
        try:
            info = self.client.get_collection(self.collection_name)
            return {
                "collection_name": self.collection_name,
                "vectors_count": info.vectors_count,
                "points_count": info.points_count,
                "status": info.status.value,
            }
        except UnexpectedResponse as e:
            if "Not found" in str(e):
                return {
                    "collection_name": self.collection_name,
                    "vectors_count": 0,
                    "points_count": 0,
                    "status": "not_initialized",
                }
            raise VectorStoreError(operation="get_stats", reason=str(e))
        except Exception as e:
            raise VectorStoreError(operation="get_stats", reason=str(e))
    
    async def get_collection_stats_async(self) -> dict[str, Any]:
        return self.get_collection_stats()
    
    def clear_collection(self) -> None:
        try:
            self.client.delete_collection(self.collection_name)
            self._initialized = False
            self.initialize()
            logger.info("Collection cleared and recreated")
        except Exception as e:
            raise VectorStoreError(operation="clear", reason=str(e))


# Singleton instance
_vector_store: VectorStore | None = None


def get_vector_store() -> VectorStore:
    global _vector_store
    if _vector_store is None:
        _vector_store = VectorStore()
    return _vector_store
