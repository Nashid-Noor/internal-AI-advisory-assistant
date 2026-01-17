#!/usr/bin/env python3

import argparse
import asyncio
import sys
from pathlib import Path
from uuid import uuid4

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.config import settings
from app.core.logging import get_logger, setup_logging
from app.ingestion.processor import DocumentProcessor
from app.ingestion.chunker import TextChunker
from app.ingestion.embedder import get_embedding_service
from app.models.documents import DocumentMetadata, DocumentType
from app.retrieval.vector_store import get_vector_store
from app.retrieval.bm25 import get_bm25_index

setup_logging()
logger = get_logger(__name__)


async def ingest_file(
    file_path: Path,
    document_type: DocumentType,
    client_name: str | None = None,
    practice_area: str | None = None,
) -> dict:
    processor = DocumentProcessor()
    chunker = TextChunker()
    embedding_service = get_embedding_service()
    vector_store = get_vector_store()
    bm25_index = get_bm25_index()
    
    document_id = uuid4()
    
    try:
        # Extract text
        extracted = processor.process_file(file_path)
        
        # Create metadata
        metadata = DocumentMetadata(
            document_id=document_id,
            filename=file_path.name,
            file_type=extracted.file_type,
            document_type=document_type,
            title=extracted.title,
            client_name=client_name,
            practice_area=practice_area,
        )
        
        # Chunk
        chunks = chunker.chunk_document(
            text=extracted.text,
            document_id=document_id,
            metadata=metadata,
        )
        
        if not chunks:
            return {
                "file": str(file_path),
                "status": "skipped",
                "reason": "No valid chunks",
            }
        
        # Embed
        chunk_texts = [chunk.content for chunk in chunks]
        embeddings = await embedding_service.embed_texts(chunk_texts)
        
        # Store in vector DB (synchronous)
        vector_store.add_chunks(chunks, embeddings)
        
        # Add to BM25 index
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
        
        return {
            "file": str(file_path),
            "status": "success",
            "document_id": str(document_id),
            "chunks": len(chunks),
        }
        
    except Exception as e:
        logger.error(f"Failed to ingest {file_path}: {e}")
        return {
            "file": str(file_path),
            "status": "error",
            "error": str(e),
        }


async def ingest_directory(
    source_dir: Path,
    document_type: DocumentType,
    client_name: str | None = None,
    practice_area: str | None = None,
) -> list[dict]:
    # Initialize vector store (synchronous)
    vector_store = get_vector_store()
    vector_store.initialize()
    
    results = []
    
    # Find all supported files
    processor = DocumentProcessor()
    for ext in processor.supported_extensions:
        for file_path in source_dir.glob(f"**/*{ext}"):
            logger.info(f"Processing: {file_path}")
            result = await ingest_file(
                file_path=file_path,
                document_type=document_type,
                client_name=client_name,
                practice_area=practice_area,
            )
            results.append(result)
    
    return results


def print_results(results: list[dict]) -> None:
    print("\n" + "=" * 60)
    print("INGESTION RESULTS")
    print("=" * 60)
    
    success = [r for r in results if r["status"] == "success"]
    errors = [r for r in results if r["status"] == "error"]
    skipped = [r for r in results if r["status"] == "skipped"]
    
    print(f"\nTotal files processed: {len(results)}")
    print(f"  ✓ Successful: {len(success)}")
    print(f"  ✗ Errors: {len(errors)}")
    print(f"  - Skipped: {len(skipped)}")
    
    total_chunks = sum(r.get("chunks", 0) for r in success)
    print(f"\nTotal chunks created: {total_chunks}")
    
    if errors:
        print("\nErrors:")
        for r in errors:
            print(f"  - {r['file']}: {r['error']}")
    
    print("=" * 60)


async def main():
    parser = argparse.ArgumentParser(
        description="Ingest documents into the knowledge base"
    )
    parser.add_argument(
        "--source",
        type=str,
        help="Source directory containing documents",
    )
    parser.add_argument(
        "--file",
        type=str,
        help="Single file to ingest",
    )
    parser.add_argument(
        "--type",
        type=str,
        default="playbook",
        choices=[t.value for t in DocumentType],
        help="Document type (default: playbook)",
    )
    parser.add_argument(
        "--client",
        type=str,
        help="Client name for the documents",
    )
    parser.add_argument(
        "--practice-area",
        type=str,
        help="Practice area for the documents",
    )
    
    args = parser.parse_args()
    
    if not args.source and not args.file:
        args.source = settings.data_raw_path
        print(f"Using default source directory: {args.source}")
    
    document_type = DocumentType(args.type)
    
    if args.file:
        # Initialize vector store (synchronous)
        vector_store = get_vector_store()
        vector_store.initialize()
        
        result = await ingest_file(
            file_path=Path(args.file),
            document_type=document_type,
            client_name=args.client,
            practice_area=args.practice_area,
        )
        print_results([result])
    else:
        source_path = Path(args.source)
        if not source_path.exists():
            print(f"Error: Source directory does not exist: {source_path}")
            sys.exit(1)
        
        results = await ingest_directory(
            source_dir=source_path,
            document_type=document_type,
            client_name=args.client,
            practice_area=args.practice_area,
        )
        print_results(results)


if __name__ == "__main__":
    asyncio.run(main())
