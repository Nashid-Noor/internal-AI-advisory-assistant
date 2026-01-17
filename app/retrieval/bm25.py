
import re
from dataclasses import dataclass, field
from typing import Any

from rank_bm25 import BM25Okapi

from app.core.logging import get_logger
from app.models.documents import RetrievedDocument

logger = get_logger(__name__)


@dataclass
class BM25Document:
    
    doc_id: str
    chunk_id: str
    content: str
    tokens: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class BM25Index:
    
    def __init__(self) -> None:
        self.documents: list[BM25Document] = []
        self.bm25: BM25Okapi | None = None
        self._needs_rebuild = True
    
    def add_documents(
        self,
        documents: list[dict[str, Any]],
    ) -> int:
        added = 0
        
        for doc in documents:
            content = doc.get("content", "")
            if not content:
                continue
            
            tokens = self._tokenize(content)
            
            bm25_doc = BM25Document(
                doc_id=doc.get("document_id", ""),
                chunk_id=doc.get("chunk_id", ""),
                content=content,
                tokens=tokens,
                metadata={
                    k: v for k, v in doc.items()
                    if k not in ("content", "chunk_id", "document_id")
                },
            )
            
            self.documents.append(bm25_doc)
            added += 1
        
        self._needs_rebuild = True
        
        logger.info(
            "Added documents to BM25 index",
            added=added,
            total=len(self.documents),
        )
        
        return added
    
    def _rebuild_index(self) -> None:
        if not self.documents:
            self.bm25 = None
            return
        
        corpus = [doc.tokens for doc in self.documents]
        self.bm25 = BM25Okapi(corpus)
        self._needs_rebuild = False
        
        logger.debug(
            "BM25 index rebuilt",
            documents=len(self.documents),
        )
    
    def search(
        self,
        query: str,
        top_k: int = 10,
        filter_dict: dict[str, Any] | None = None,
    ) -> list[RetrievedDocument]:
        if self._needs_rebuild:
            self._rebuild_index()
        
        if not self.bm25 or not self.documents:
            return []
        
        # Tokenize query
        query_tokens = self._tokenize(query)
        
        if not query_tokens:
            return []
        
        # Get BM25 scores for all documents
        scores = self.bm25.get_scores(query_tokens)
        
        # Apply filters if provided
        if filter_dict:
            scores = self._apply_filters(scores, filter_dict)
        
        # Get top-k indices
        top_indices = sorted(
            range(len(scores)),
            key=lambda i: scores[i],
            reverse=True,
        )[:top_k]
        
        # Build results
        results = []
        for rank, idx in enumerate(top_indices):
            if scores[idx] <= 0:
                continue
            
            doc = self.documents[idx]
            
            # Normalize score to 0-1 range (approximate)
            normalized_score = min(scores[idx] / 30.0, 1.0)
            
            results.append(RetrievedDocument(
                chunk_id=doc.chunk_id,
                document_id=doc.doc_id,
                content=doc.content,
                score=normalized_score,
                rank=rank,
                filename=doc.metadata.get("filename", ""),
                document_type=doc.metadata.get("document_type", ""),
                title=doc.metadata.get("title"),
                section_title=doc.metadata.get("section_title"),
                chunk_index=doc.metadata.get("chunk_index", 0),
            ))
        
        logger.debug(
            "BM25 search completed",
            query_tokens=len(query_tokens),
            results=len(results),
        )
        
        return results
    
    def _apply_filters(
        self,
        scores: list[float],
        filter_dict: dict[str, Any],
    ) -> list[float]:
        filtered_scores = list(scores)
        
        for idx, doc in enumerate(self.documents):
            for field, allowed_values in filter_dict.items():
                doc_value = doc.metadata.get(field)
                
                if isinstance(allowed_values, list):
                    if doc_value not in allowed_values:
                        filtered_scores[idx] = 0.0
                        break
                else:
                    if doc_value != allowed_values:
                        filtered_scores[idx] = 0.0
                        break
        
        return filtered_scores
    
    def _tokenize(self, text: str) -> list[str]:
        # Lowercase
        text = text.lower()
        
        # Split on non-alphanumeric characters
        tokens = re.findall(r"\b[a-z0-9]+\b", text)
        
        # Filter short tokens (but keep numbers)
        tokens = [t for t in tokens if len(t) > 2 or t.isdigit()]
        
        return tokens
    
    def remove_document(self, chunk_id: str) -> bool:
        original_length = len(self.documents)
        self.documents = [d for d in self.documents if d.chunk_id != chunk_id]
        
        if len(self.documents) < original_length:
            self._needs_rebuild = True
            return True
        return False
    
    def clear(self) -> None:
        self.documents = []
        self.bm25 = None
        self._needs_rebuild = True
        logger.info("BM25 index cleared")
    
    def get_stats(self) -> dict[str, Any]:
        return {
            "document_count": len(self.documents),
            "needs_rebuild": self._needs_rebuild,
            "avg_doc_length": (
                sum(len(d.tokens) for d in self.documents) / len(self.documents)
                if self.documents else 0
            ),
        }


# Singleton instance
_bm25_index: BM25Index | None = None


def get_bm25_index() -> BM25Index:
    global _bm25_index
    if _bm25_index is None:
        _bm25_index = BM25Index()
    return _bm25_index
