
import re
from dataclasses import dataclass, field
from typing import Iterator
from uuid import UUID, uuid4

import tiktoken

from app.core.config import settings
from app.core.logging import get_logger
from app.models.documents import DocumentChunk, DocumentMetadata

logger = get_logger(__name__)


@dataclass
class ChunkingConfig:
    
    # Size parameters (in tokens)
    target_size: int = 512
    min_size: int = 100
    max_size: int = 1024
    overlap: int = 64
    
    # Behavior flags
    respect_sentence_boundaries: bool = True
    respect_paragraph_boundaries: bool = True
    preserve_headings: bool = True
    
    @classmethod
    def from_settings(cls) -> "ChunkingConfig":
        return cls(
            target_size=settings.chunk_size,
            min_size=settings.min_chunk_size,
            overlap=settings.chunk_overlap,
        )


@dataclass
class TextSegment:
    
    text: str
    segment_type: str = "paragraph"  # paragraph, heading, list, code, table
    heading_level: int | None = None
    start_char: int = 0
    end_char: int = 0


class TextChunker:
    
    def __init__(
        self,
        config: ChunkingConfig | None = None,
        tokenizer_name: str = "cl100k_base",
    ) -> None:
        self.config = config or ChunkingConfig.from_settings()
        
        # Initialize tokenizer for accurate token counting
        try:
            self.tokenizer = tiktoken.get_encoding(tokenizer_name)
        except Exception:
            logger.warning(
                "Failed to load tiktoken, using approximate token counting"
            )
            self.tokenizer = None
    
    def count_tokens(self, text: str) -> int:
        if self.tokenizer:
            return len(self.tokenizer.encode(text))
        else:
            # Approximate: ~4 characters per token for English
            return len(text) // 4
    
    def chunk_document(
        self,
        text: str,
        document_id: UUID,
        metadata: DocumentMetadata,
    ) -> list[DocumentChunk]:
        if not text.strip():
            logger.warning("Empty document received for chunking")
            return []
        
        # First, segment the text into semantic units
        segments = self._segment_text(text)
        
        # Then, combine segments into appropriately-sized chunks
        chunks = self._create_chunks(segments, document_id, metadata)
        
        logger.info(
            "Document chunked",
            document_id=str(document_id),
            segments=len(segments),
            chunks=len(chunks),
        )
        
        return chunks
    
    def _segment_text(self, text: str) -> list[TextSegment]:
        segments = []
        current_pos = 0
        
        # Split into paragraphs/blocks first
        blocks = re.split(r"\n\s*\n", text)
        
        for block in blocks:
            block = block.strip()
            if not block:
                continue
            
            # Determine segment type
            segment_type, heading_level = self._classify_segment(block)
            
            # Find position in original text
            start_pos = text.find(block, current_pos)
            if start_pos == -1:
                start_pos = current_pos
            end_pos = start_pos + len(block)
            current_pos = end_pos
            
            segments.append(TextSegment(
                text=block,
                segment_type=segment_type,
                heading_level=heading_level,
                start_char=start_pos,
                end_char=end_pos,
            ))
        
        return segments
    
    def _classify_segment(self, text: str) -> tuple[str, int | None]:
        lines = text.split("\n")
        first_line = lines[0].strip()
        
        # Check for markdown headings
        heading_match = re.match(r"^(#{1,6})\s+", first_line)
        if heading_match:
            level = len(heading_match.group(1))
            return "heading", level
        
        # Check for underlined headings
        if len(lines) >= 2:
            if re.match(r"^=+$", lines[1].strip()):
                return "heading", 1
            if re.match(r"^-+$", lines[1].strip()):
                return "heading", 2
        
        # Check for ALL CAPS headings (common in legal/policy docs)
        if first_line.isupper() and len(first_line) < 100:
            return "heading", 2
        
        # Check for lists
        if re.match(r"^[\-\*\+]\s", first_line) or re.match(r"^\d+[\.\)]\s", first_line):
            return "list", None
        
        # Check for code blocks
        if text.startswith("```") or text.startswith("    "):
            return "code", None
        
        # Default to paragraph
        return "paragraph", None
    
    def _create_chunks(
        self,
        segments: list[TextSegment],
        document_id: UUID,
        metadata: DocumentMetadata,
    ) -> list[DocumentChunk]:
        chunks = []
        current_chunk_text = ""
        current_chunk_segments: list[TextSegment] = []
        chunk_index = 0
        current_heading_hierarchy: list[str] = []
        current_section_title: str | None = None
        
        for segment in segments:
            # Update heading hierarchy
            if segment.segment_type == "heading" and segment.heading_level:
                heading_text = self._clean_heading(segment.text)
                level = segment.heading_level
                
                # Trim hierarchy to current level
                current_heading_hierarchy = current_heading_hierarchy[:level - 1]
                current_heading_hierarchy.append(heading_text)
                current_section_title = heading_text
            
            segment_tokens = self.count_tokens(segment.text)
            current_tokens = self.count_tokens(current_chunk_text)
            
            # Check if adding this segment would exceed target size
            if current_tokens + segment_tokens > self.config.target_size:
                # Save current chunk if it has content
                if current_chunk_text.strip():
                    chunks.append(self._create_chunk(
                        text=current_chunk_text,
                        chunk_index=chunk_index,
                        document_id=document_id,
                        metadata=metadata,
                        heading_hierarchy=list(current_heading_hierarchy),
                        section_title=current_section_title,
                        start_char=current_chunk_segments[0].start_char if current_chunk_segments else 0,
                        end_char=current_chunk_segments[-1].end_char if current_chunk_segments else 0,
                    ))
                    chunk_index += 1
                
                # Start new chunk with overlap
                overlap_text = self._get_overlap_text(current_chunk_text)
                current_chunk_text = overlap_text
                current_chunk_segments = []
            
            # Handle segments that are too large on their own
            if segment_tokens > self.config.max_size:
                # Split large segment
                sub_chunks = self._split_large_segment(segment)
                for sub_chunk in sub_chunks:
                    if current_chunk_text.strip():
                        current_chunk_text += "\n\n"
                    current_chunk_text += sub_chunk
                    current_chunk_segments.append(segment)
                    
                    if self.count_tokens(current_chunk_text) >= self.config.target_size:
                        chunks.append(self._create_chunk(
                            text=current_chunk_text,
                            chunk_index=chunk_index,
                            document_id=document_id,
                            metadata=metadata,
                            heading_hierarchy=list(current_heading_hierarchy),
                            section_title=current_section_title,
                            start_char=segment.start_char,
                            end_char=segment.end_char,
                        ))
                        chunk_index += 1
                        
                        overlap_text = self._get_overlap_text(current_chunk_text)
                        current_chunk_text = overlap_text
                        current_chunk_segments = []
            else:
                # Add segment to current chunk
                if current_chunk_text.strip():
                    current_chunk_text += "\n\n"
                current_chunk_text += segment.text
                current_chunk_segments.append(segment)
        
        # Don't forget the last chunk
        if current_chunk_text.strip() and self.count_tokens(current_chunk_text) >= self.config.min_size:
            chunks.append(self._create_chunk(
                text=current_chunk_text,
                chunk_index=chunk_index,
                document_id=document_id,
                metadata=metadata,
                heading_hierarchy=list(current_heading_hierarchy),
                section_title=current_section_title,
                start_char=current_chunk_segments[0].start_char if current_chunk_segments else 0,
                end_char=current_chunk_segments[-1].end_char if current_chunk_segments else 0,
            ))
        
        return chunks
    
    def _create_chunk(
        self,
        text: str,
        chunk_index: int,
        document_id: UUID,
        metadata: DocumentMetadata,
        heading_hierarchy: list[str],
        section_title: str | None,
        start_char: int,
        end_char: int,
    ) -> DocumentChunk:
        return DocumentChunk(
            chunk_id=uuid4(),
            document_id=document_id,
            content=text.strip(),
            chunk_index=chunk_index,
            start_char=start_char,
            end_char=end_char,
            section_title=section_title,
            heading_hierarchy=heading_hierarchy,
            document_metadata=metadata,
            token_count=self.count_tokens(text),
        )
    
    def _get_overlap_text(self, text: str) -> str:
        if not text or self.config.overlap == 0:
            return ""
        
        # Get approximate character count for overlap
        overlap_chars = self.config.overlap * 4  # Approximate tokens to chars
        
        if len(text) <= overlap_chars:
            return text
        
        # Take last N characters
        overlap_text = text[-overlap_chars:]
        
        # Try to start at a sentence boundary
        if self.config.respect_sentence_boundaries:
            sentence_start = re.search(r"[.!?]\s+", overlap_text)
            if sentence_start:
                overlap_text = overlap_text[sentence_start.end():]
        
        return overlap_text
    
    def _split_large_segment(self, segment: TextSegment) -> list[str]:
        text = segment.text
        target_tokens = self.config.target_size - self.config.overlap
        
        # Split on sentences
        sentences = re.split(r"(?<=[.!?])\s+", text)
        
        chunks = []
        current_chunk = ""
        
        for sentence in sentences:
            if self.count_tokens(current_chunk + " " + sentence) > target_tokens:
                if current_chunk:
                    chunks.append(current_chunk)
                current_chunk = sentence
            else:
                if current_chunk:
                    current_chunk += " " + sentence
                else:
                    current_chunk = sentence
        
        if current_chunk:
            chunks.append(current_chunk)
        
        return chunks
    
    def _clean_heading(self, text: str) -> str:
        # Remove markdown heading markers
        text = re.sub(r"^#+\s*", "", text)
        # Remove underline markers
        text = re.sub(r"\n[=-]+$", "", text)
        return text.strip()
