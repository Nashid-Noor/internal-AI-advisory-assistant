
import time
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, File, HTTPException, UploadFile, status

from app.api.dependencies import CurrentUser, VectorDB
from app.core.config import settings
from app.core.logging import get_logger
from app.core.security import UserRole, require_role
from app.ingestion.chunker import TextChunker
from app.ingestion.embedder import get_embedding_service
from app.ingestion.processor import DocumentProcessor
from app.models.documents import (
    DocumentIngestionResult,
    DocumentMetadata,
    DocumentType,
    DocumentUpload,
)
from app.retrieval.bm25 import get_bm25_index

logger = get_logger(__name__)

router = APIRouter(prefix="/ingest", tags=["Ingestion"])


@router.post(
    "/document",
    response_model=DocumentIngestionResult,
    summary="Ingest a single document",
    description="Upload and process a document into the knowledge base",
)
async def ingest_document(
    document: DocumentUpload,
    user: CurrentUser,
    vector_store: VectorDB,
) -> DocumentIngestionResult:
    start_time = time.time()
    errors: list[str] = []
    warnings: list[str] = []
    
    # Validate document type access
    doc_type_role = _get_required_role_for_type(document.document_type)
    if not user.role.can_access(doc_type_role):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"You need '{doc_type_role.value}' role to ingest {document.document_type.value} documents",
        )
    
    document_id = uuid4()
    
    try:
        # Get document content
        if document.file_path:
            file_path = Path(document.file_path)
            if not file_path.exists():
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"File not found: {document.file_path}",
                )
        elif document.content_base64:
            # Decode and save to temp file
            import base64
            import tempfile
            
            content = base64.b64decode(document.content_base64)
            suffix = Path(document.filename).suffix
            
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as f:
                f.write(content)
                file_path = Path(f.name)
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Either file_path or content_base64 must be provided",
            )
        
        # Process document
        processor = DocumentProcessor()
        extracted = processor.process_file(file_path)
        
        if extracted.extraction_warnings:
            warnings.extend(extracted.extraction_warnings)
        
        # Create metadata
        metadata = DocumentMetadata(
            document_id=document_id,
            filename=document.filename,
            file_type=extracted.file_type,
            document_type=document.document_type,
            title=document.title or extracted.title,
            client_name=document.client_name,
            practice_area=document.practice_area,
            author=document.author,
            tags=document.tags,
        )
        
        # Chunk document
        chunker = TextChunker()
        chunks = chunker.chunk_document(
            text=extracted.text,
            document_id=document_id,
            metadata=metadata,
        )
        
        if not chunks:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Document produced no valid chunks",
            )
        
        # Generate embeddings
        embedding_service = get_embedding_service()
        chunk_texts = [chunk.content for chunk in chunks]
        embeddings = await embedding_service.embed_texts(chunk_texts, show_progress=True)
        
        # Store in vector database (synchronous)
        vector_store.add_chunks(chunks, embeddings)
        
        # Add to BM25 index
        bm25_index = get_bm25_index()
        bm25_docs = [
            {
                "chunk_id": str(chunk.chunk_id),
                "document_id": str(chunk.document_id),
                "content": chunk.content,
                "filename": metadata.filename,
                "document_type": metadata.document_type.value,
                "title": metadata.title,
                "section_title": chunk.section_title,
                "chunk_index": chunk.chunk_index,
            }
            for chunk in chunks
        ]
        bm25_index.add_documents(bm25_docs)
        
        processing_time = int((time.time() - start_time) * 1000)
        
        logger.info(
            "Document ingested",
            document_id=str(document_id),
            filename=document.filename,
            chunks=len(chunks),
            processing_time_ms=processing_time,
        )
        
        return DocumentIngestionResult(
            document_id=document_id,
            filename=document.filename,
            status="success",
            chunks_created=len(chunks),
            errors=errors,
            warnings=warnings,
            processing_time_ms=processing_time,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Ingestion failed",
            filename=document.filename,
            error=str(e),
        )
        
        processing_time = int((time.time() - start_time) * 1000)
        
        return DocumentIngestionResult(
            document_id=document_id,
            filename=document.filename,
            status="failed",
            chunks_created=0,
            errors=[str(e)],
            warnings=warnings,
            processing_time_ms=processing_time,
        )


@router.post(
    "/upload",
    response_model=DocumentIngestionResult,
    summary="Upload and ingest a file",
)
async def upload_document(
    file: UploadFile = File(...),
    document_type: DocumentType = DocumentType.PLAYBOOK,
    title: str | None = None,
    client_name: str | None = None,
    practice_area: str | None = None,
    user: CurrentUser = None,
    vector_store: VectorDB = None,
) -> DocumentIngestionResult:
    import base64
    
    content = await file.read()
    content_base64 = base64.b64encode(content).decode()
    
    upload = DocumentUpload(
        filename=file.filename or "uploaded_file",
        content_base64=content_base64,
        document_type=document_type,
        title=title,
        client_name=client_name,
        practice_area=practice_area,
    )
    
    return await ingest_document(upload, user, vector_store)


@router.get(
    "/stats",
    summary="Get ingestion statistics",
)
async def get_stats(
    vector_store: VectorDB,
) -> dict[str, Any]:
    vector_stats = vector_store.get_collection_stats()  # Synchronous
    bm25_stats = get_bm25_index().get_stats()
    
    return {
        "vector_store": vector_stats,
        "bm25_index": bm25_stats,
    }


def _get_required_role_for_type(doc_type: DocumentType) -> UserRole:
    partner_types = {
        DocumentType.PARTNER_MEMO,
        DocumentType.FEE_STRUCTURE,
        DocumentType.STRATEGIC_PLAN,
        DocumentType.CONFIDENTIAL,
    }
    
    consultant_types = {
        DocumentType.CLIENT_SUMMARY,
        DocumentType.ENGAGEMENT,
        DocumentType.PROPOSAL,
    }
    
    if doc_type in partner_types:
        return UserRole.PARTNER
    elif doc_type in consultant_types:
        return UserRole.CONSULTANT
    else:
        return UserRole.ANALYST
