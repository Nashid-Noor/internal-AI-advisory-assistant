"""
Tests for Text Chunker
"""

import pytest
from uuid import uuid4

from app.ingestion.chunker import TextChunker, ChunkingConfig
from app.models.documents import DocumentMetadata, DocumentType


@pytest.fixture
def chunker():
    """Create a chunker with test configuration."""
    config = ChunkingConfig(
        target_size=100,
        min_size=20,
        max_size=200,
        overlap=10,
    )
    return TextChunker(config=config)


@pytest.fixture
def sample_metadata():
    """Create sample document metadata."""
    return DocumentMetadata(
        document_id=uuid4(),
        filename="test_document.md",
        file_type="md",
        document_type=DocumentType.PLAYBOOK,
    )


class TestTextChunker:
    """Tests for TextChunker class."""
    
    def test_empty_document(self, chunker, sample_metadata):
        """Empty documents should produce no chunks."""
        chunks = chunker.chunk_document(
            text="",
            document_id=sample_metadata.document_id,
            metadata=sample_metadata,
        )
        assert len(chunks) == 0
    
    def test_whitespace_only_document(self, chunker, sample_metadata):
        """Whitespace-only documents should produce no chunks."""
        chunks = chunker.chunk_document(
            text="   \n\n\t  ",
            document_id=sample_metadata.document_id,
            metadata=sample_metadata,
        )
        assert len(chunks) == 0
    
    def test_short_document(self, chunker, sample_metadata):
        """Short documents that fit in one chunk."""
        text = "This is a short test document with minimal content."
        chunks = chunker.chunk_document(
            text=text,
            document_id=sample_metadata.document_id,
            metadata=sample_metadata,
        )
        
        assert len(chunks) >= 1
        assert text in chunks[0].content
    
    def test_document_with_headings(self, chunker, sample_metadata):
        """Documents with markdown headings should track heading hierarchy."""
        text = """# Main Title

This is the introduction.

## Section One

Content for section one.

## Section Two

Content for section two.

### Subsection

Nested content here.
"""
        chunks = chunker.chunk_document(
            text=text,
            document_id=sample_metadata.document_id,
            metadata=sample_metadata,
        )
        
        assert len(chunks) >= 1
        # Verify heading tracking works
        # At least some chunks should have section titles
        has_section_title = any(c.section_title is not None for c in chunks)
        assert has_section_title or len(chunks) == 1
    
    def test_chunk_indices_are_sequential(self, chunker, sample_metadata):
        """Chunk indices should be sequential starting from 0."""
        text = "First paragraph. " * 50 + "\n\n" + "Second paragraph. " * 50
        chunks = chunker.chunk_document(
            text=text,
            document_id=sample_metadata.document_id,
            metadata=sample_metadata,
        )
        
        indices = [c.chunk_index for c in chunks]
        assert indices == list(range(len(chunks)))
    
    def test_chunks_have_document_reference(self, chunker, sample_metadata):
        """All chunks should reference the source document."""
        text = "Test content. " * 100
        chunks = chunker.chunk_document(
            text=text,
            document_id=sample_metadata.document_id,
            metadata=sample_metadata,
        )
        
        for chunk in chunks:
            assert chunk.document_id == sample_metadata.document_id
    
    def test_chunks_have_metadata(self, chunker, sample_metadata):
        """All chunks should include document metadata."""
        text = "Test content with metadata."
        chunks = chunker.chunk_document(
            text=text,
            document_id=sample_metadata.document_id,
            metadata=sample_metadata,
        )
        
        for chunk in chunks:
            assert chunk.document_metadata.filename == "test_document.md"
            assert chunk.document_metadata.document_type == DocumentType.PLAYBOOK


class TestTokenCounting:
    """Tests for token counting functionality."""
    
    def test_count_tokens_empty(self, chunker):
        """Empty string should have 0 tokens."""
        assert chunker.count_tokens("") == 0
    
    def test_count_tokens_basic(self, chunker):
        """Basic token counting."""
        text = "Hello world"
        count = chunker.count_tokens(text)
        # Should be approximately 2-3 tokens
        assert 1 <= count <= 5
    
    def test_count_tokens_longer_text(self, chunker):
        """Longer text should have more tokens."""
        short_text = "Hello"
        long_text = "Hello world this is a longer sentence with more words"
        
        short_count = chunker.count_tokens(short_text)
        long_count = chunker.count_tokens(long_text)
        
        assert long_count > short_count
