
from dataclasses import dataclass
from typing import Any

from app.core.config import settings
from app.core.logging import get_logger
from app.core.security import RoleBasedFilter, UserRole, get_role_filter
from app.ingestion.embedder import EmbeddingService, get_embedding_service
from app.models.documents import RetrievedDocument
from app.retrieval.bm25 import BM25Index, get_bm25_index
from app.retrieval.vector_store import VectorStore, get_vector_store

logger = get_logger(__name__)


@dataclass
class HybridSearchConfig:
    
    dense_weight: float = 0.7
    sparse_weight: float = 0.3
    rrf_k: int = 60  # RRF constant
    
    # Whether to use each retrieval method
    use_dense: bool = True
    use_sparse: bool = True
    
    @classmethod
    def from_settings(cls) -> "HybridSearchConfig":
        return cls(
            dense_weight=settings.hybrid_dense_weight,
            sparse_weight=settings.hybrid_sparse_weight,
            rrf_k=settings.rrf_k,
            use_sparse=settings.hybrid_enabled,
        )


class HybridRetriever:
    
    def __init__(
        self,
        vector_store: VectorStore | None = None,
        bm25_index: BM25Index | None = None,
        embedding_service: EmbeddingService | None = None,
        config: HybridSearchConfig | None = None,
    ) -> None:
        self.vector_store = vector_store or get_vector_store()
        self.bm25_index = bm25_index or get_bm25_index()
        self.embedding_service = embedding_service or get_embedding_service()
        self.config = config or HybridSearchConfig.from_settings()
    
    async def retrieve(
        self,
        query: str,
        user_role: UserRole,
        top_k: int = 10,
        client_name: str | None = None,
        practice_area: str | None = None,
        document_types: list[str] | None = None,
    ) -> list[RetrievedDocument]:
        # Build filter dict for role-based access control
        accessible_types = get_role_filter(user_role)
        
        # If document_types specified, intersect with accessible
        if document_types:
            allowed_types = [t for t in document_types if t in accessible_types]
        else:
            allowed_types = accessible_types
        
        filter_dict: dict[str, Any] = {
            "document_type": allowed_types,
        }
        
        if client_name:
            filter_dict["client_name"] = client_name
        if practice_area:
            filter_dict["practice_area"] = practice_area
        
        logger.info(
            "Starting hybrid retrieval",
            query_length=len(query),
            user_role=user_role.value,
            filters=list(filter_dict.keys()),
        )
        
        # Fetch more than top_k from each source for better fusion
        fetch_k = min(top_k * 2, 50)
        
        dense_results: list[RetrievedDocument] = []
        sparse_results: list[RetrievedDocument] = []
        
        # Dense retrieval (vector search)
        if self.config.use_dense:
            try:
                query_embedding = await self.embedding_service.embed_text(query)
                # vector_store.search is synchronous
                dense_results = self.vector_store.search(
                    query_embedding=query_embedding,
                    top_k=fetch_k,
                    filter_dict=filter_dict,
                )
                logger.debug(
                    "Dense retrieval completed",
                    results=len(dense_results),
                )
            except Exception as e:
                logger.warning(
                    "Dense retrieval failed, falling back to sparse only",
                    error=str(e),
                )
        
        # Sparse retrieval (BM25)
        if self.config.use_sparse:
            try:
                sparse_results = self.bm25_index.search(
                    query=query,
                    top_k=fetch_k,
                    filter_dict=filter_dict,
                )
                logger.debug(
                    "Sparse retrieval completed",
                    results=len(sparse_results),
                )
            except Exception as e:
                logger.warning(
                    "Sparse retrieval failed",
                    error=str(e),
                )
        
        # If only one method returned results, use those
        if not dense_results and not sparse_results:
            logger.warning("No results from any retrieval method")
            return []
        
        if not dense_results:
            return sparse_results[:top_k]
        
        if not sparse_results:
            return dense_results[:top_k]
        
        # Combine using Reciprocal Rank Fusion
        fused_results = self._reciprocal_rank_fusion(
            dense_results=dense_results,
            sparse_results=sparse_results,
        )
        
        # Return top_k results
        return fused_results[:top_k]
    
    def _reciprocal_rank_fusion(
        self,
        dense_results: list[RetrievedDocument],
        sparse_results: list[RetrievedDocument],
    ) -> list[RetrievedDocument]:
        k = self.config.rrf_k
        
        # Calculate RRF scores
        # Key: chunk_id, Value: (score, document)
        scores: dict[str, tuple[float, RetrievedDocument]] = {}
        
        # Add dense scores
        for doc in dense_results:
            rrf_score = self.config.dense_weight / (k + doc.rank)
            scores[doc.chunk_id] = (rrf_score, doc)
        
        # Add sparse scores
        for doc in sparse_results:
            rrf_score = self.config.sparse_weight / (k + doc.rank)
            
            if doc.chunk_id in scores:
                # Combine scores
                existing_score, existing_doc = scores[doc.chunk_id]
                combined_score = existing_score + rrf_score
                scores[doc.chunk_id] = (combined_score, existing_doc)
            else:
                scores[doc.chunk_id] = (rrf_score, doc)
        
        # Sort by combined score
        sorted_items = sorted(
            scores.items(),
            key=lambda x: x[1][0],
            reverse=True,
        )
        
        # Build result list with updated ranks and scores
        results = []
        for rank, (chunk_id, (score, doc)) in enumerate(sorted_items):
            # Create new document with fused score
            fused_doc = RetrievedDocument(
                chunk_id=doc.chunk_id,
                document_id=doc.document_id,
                content=doc.content,
                score=min(score * 10, 1.0),  # Normalize to 0-1
                rank=rank,
                filename=doc.filename,
                document_type=doc.document_type,
                title=doc.title,
                section_title=doc.section_title,
                chunk_index=doc.chunk_index,
                client_name=doc.client_name,
                practice_area=doc.practice_area,
                tags=doc.tags,
            )
            results.append(fused_doc)
        
        logger.debug(
            "RRF fusion completed",
            unique_docs=len(results),
            top_score=results[0].score if results else 0,
        )
        
        return results
    
    async def retrieve_for_context(
        self,
        query: str,
        user_role: UserRole,
        max_tokens: int = 4000,
        **kwargs,
    ) -> tuple[list[RetrievedDocument], str]:
        # Estimate tokens per document
        docs_to_fetch = max(max_tokens // 500, 3)
        
        documents = await self.retrieve(
            query=query,
            user_role=user_role,
            top_k=docs_to_fetch,
            **kwargs,
        )
        
        # Format context
        context_parts = []
        for i, doc in enumerate(documents):
            source_info = f"[Source {i+1}: {doc.filename}"
            if doc.section_title:
                source_info += f" - {doc.section_title}"
            source_info += "]"
            
            context_parts.append(f"{source_info}\n{doc.content}")
        
        context = "\n\n---\n\n".join(context_parts)
        
        return documents, context


# Singleton instance
_hybrid_retriever: HybridRetriever | None = None


def get_hybrid_retriever() -> HybridRetriever:
    global _hybrid_retriever
    if _hybrid_retriever is None:
        _hybrid_retriever = HybridRetriever()
    return _hybrid_retriever
