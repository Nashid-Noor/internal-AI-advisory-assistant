
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator


class TaskType(str, Enum):
    
    # General Q&A
    QUESTION_ANSWER = "question_answer"
    
    # Client-focused tasks
    SUMMARIZE_CLIENT = "summarize_client"
    CLIENT_BACKGROUND = "client_background"
    
    # Risk & Analysis
    RISK_ANALYSIS = "risk_analysis"
    OPPORTUNITY_ANALYSIS = "opportunity_analysis"
    
    # Recommendations
    DRAFT_RECOMMENDATIONS = "draft_recommendations"
    ACTION_ITEMS = "action_items"
    
    # Executive communication
    EXECUTIVE_SUMMARY = "executive_summary"
    TALKING_POINTS = "talking_points"
    
    # Comparison & Research
    COMPARE_APPROACHES = "compare_approaches"
    RESEARCH_TOPIC = "research_topic"


class QueryRequest(BaseModel):
    
    # Core query
    query: str = Field(
        ...,
        min_length=3,
        max_length=2000,
        description="The user's question or request",
    )
    
    # Optional task specification
    task_type: TaskType | None = Field(
        default=None,
        description="Explicit task type. If not provided, will be auto-detected.",
    )
    
    # Context filters
    client_name: str | None = Field(
        default=None,
        description="Filter results to specific client",
    )
    practice_area: str | None = Field(
        default=None,
        description="Filter results to specific practice area",
    )
    document_types: list[str] | None = Field(
        default=None,
        description="Filter to specific document types",
    )
    
    # Retrieval parameters
    max_sources: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Maximum number of source documents to retrieve",
    )
    
    # Output preferences
    response_format: str = Field(
        default="structured",
        description="'structured' for JSON output, 'narrative' for prose",
    )
    include_sources: bool = Field(
        default=True,
        description="Whether to include source citations",
    )
    
    # Request metadata
    request_id: UUID = Field(default_factory=uuid4)
    
    @field_validator("query")
    @classmethod
    def validate_query(cls, v: str) -> str:
        # Strip whitespace
        v = v.strip()
        
        # Ensure minimum content
        if len(v.split()) < 2:
            raise ValueError("Query must contain at least 2 words")
        
        return v


class QueryMetrics(BaseModel):
    
    total_time_ms: int
    retrieval_time_ms: int
    generation_time_ms: int
    
    # Retrieval stats
    documents_retrieved: int
    documents_used: int
    
    # Intent detection
    intent_detected: str | None = None
    intent_confidence: float | None = None


class SourceDocument(BaseModel):
    
    document_id: str
    filename: str
    title: str | None = None
    document_type: str
    section: str | None = None
    relevance_score: float
    
    # Preview of relevant content
    excerpt: str = Field(
        default="",
        max_length=300,
        description="Brief excerpt from the source",
    )


class QueryResponse(BaseModel):
    
    # Request tracking
    request_id: UUID
    
    # Status
    success: bool = True
    error: str | None = None
    
    # Core response
    response: dict[str, Any] | str = Field(
        ...,
        description="Structured response object or narrative string",
    )
    
    # Task information
    task_type: TaskType
    query: str
    
    # Sources
    sources: list[SourceDocument] = Field(
        default_factory=list,
        description="Source documents used to generate response",
    )
    
    # Quality indicators
    confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Model's confidence in the response",
    )
    
    # Metadata
    metrics: QueryMetrics | None = None
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # User context (for audit)
    user_role: str | None = None


class ConversationContext(BaseModel):
    
    conversation_id: UUID = Field(default_factory=uuid4)
    
    # Previous turns
    previous_queries: list[str] = Field(
        default_factory=list,
        max_length=10,  # Limit context window
    )
    previous_responses: list[str] = Field(
        default_factory=list,
        max_length=10,
    )
    
    # Accumulated context
    mentioned_clients: list[str] = Field(default_factory=list)
    mentioned_topics: list[str] = Field(default_factory=list)
    
    # Session metadata
    started_at: datetime = Field(default_factory=datetime.utcnow)


class StreamingChunk(BaseModel):
    
    chunk_type: str = Field(
        default="text",
        description="'text' for content, 'status' for progress updates",
    )
    content: str
    is_final: bool = False
    
    # Progress tracking (for status chunks)
    stage: str | None = None  # e.g., "retrieving", "generating"
    progress: float | None = None  # 0.0 to 1.0
