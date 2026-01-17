from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class DocumentType(str, Enum):
    # Analyst
    PLAYBOOK = "playbook"
    GUIDELINE = "guideline"
    TEMPLATE = "template"
    TRAINING = "training"
    
    # Consultant
    CLIENT_SUMMARY = "client_summary"
    ENGAGEMENT = "engagement"
    PROPOSAL = "proposal"
    
    # Partner
    PARTNER_MEMO = "partner_memo"
    FEE_STRUCTURE = "fee_structure"
    STRATEGIC_PLAN = "strategic_plan"
    CONFIDENTIAL = "confidential"


class DocumentMetadata(BaseModel):
    document_id: UUID = Field(default_factory=uuid4)
    filename: str
    file_type: str
    
    document_type: DocumentType
    title: str | None = None
    
    client_name: str | None = None
    practice_area: str | None = None
    author: str | None = None
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime | None = None
    effective_date: datetime | None = None
    
    ingested_at: datetime = Field(default_factory=datetime.utcnow)
    chunk_count: int = 0
    
    tags: list[str] = Field(default_factory=list)
    custom_metadata: dict[str, Any] = Field(default_factory=dict)
    
    def to_vector_payload(self) -> dict[str, Any]:
        return {
            "document_id": str(self.document_id),
            "filename": self.filename,
            "file_type": self.file_type,
            "document_type": self.document_type.value,
            "title": self.title,
            "client_name": self.client_name,
            "practice_area": self.practice_area,
            "author": self.author,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "tags": self.tags,
        }


class DocumentChunk(BaseModel):
    chunk_id: UUID = Field(default_factory=uuid4)
    document_id: UUID
    
    content: str
    
    chunk_index: int
    start_char: int | None = None
    end_char: int | None = None
    
    section_title: str | None = None
    heading_hierarchy: list[str] = Field(default_factory=list)
    
    document_metadata: DocumentMetadata
    token_count: int | None = None
    
    def to_vector_payload(self) -> dict[str, Any]:
        payload = self.document_metadata.to_vector_payload()
        payload.update({
            "chunk_id": str(self.chunk_id),
            "chunk_index": self.chunk_index,
            "section_title": self.section_title,
            "heading_hierarchy": self.heading_hierarchy,
            "content_preview": self.content[:200],
        })
        return payload


class RetrievedDocument(BaseModel):
    chunk_id: str
    document_id: str
    content: str
    
    score: float
    rank: int
    
    filename: str
    document_type: str
    title: str | None = None
    
    section_title: str | None = None
    chunk_index: int = 0
    
    client_name: str | None = None
    practice_area: str | None = None
    tags: list[str] = Field(default_factory=list)
    
    @classmethod
    def from_search_result(
        cls,
        content: str,
        score: float,
        rank: int,
        payload: dict[str, Any],
    ) -> "RetrievedDocument":
        return cls(
            chunk_id=payload.get("chunk_id", ""),
            document_id=payload.get("document_id", ""),
            content=content,
            score=score,
            rank=rank,
            filename=payload.get("filename", ""),
            document_type=payload.get("document_type", ""),
            title=payload.get("title"),
            section_title=payload.get("section_title"),
            chunk_index=payload.get("chunk_index", 0),
            client_name=payload.get("client_name"),
            practice_area=payload.get("practice_area"),
            tags=payload.get("tags", []),
        )
    
    def to_citation(self) -> dict[str, Any]:
        return {
            "document_id": self.document_id,
            "filename": self.filename,
            "title": self.title or self.filename,
            "section": self.section_title,
            "relevance_score": round(self.score, 3),
        }


class DocumentUpload(BaseModel):
    filename: str
    content_base64: str | None = None
    file_path: str | None = None
    
    document_type: DocumentType
    
    title: str | None = None
    client_name: str | None = None
    practice_area: str | None = None
    author: str | None = None
    tags: list[str] = Field(default_factory=list)


class DocumentIngestionResult(BaseModel):
    document_id: UUID
    filename: str
    status: str
    chunks_created: int
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    processing_time_ms: int
