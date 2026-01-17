
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class FeedbackRating(str, Enum):
    
    POSITIVE = "positive"  # 👍
    NEGATIVE = "negative"  # 👎


class FeedbackCategory(str, Enum):
    
    # Response quality
    INCORRECT_INFORMATION = "incorrect_information"
    INCOMPLETE_ANSWER = "incomplete_answer"
    IRRELEVANT_RESPONSE = "irrelevant_response"
    
    # Retrieval issues
    WRONG_SOURCES = "wrong_sources"
    MISSING_SOURCES = "missing_sources"
    
    # Format/presentation
    POOR_FORMATTING = "poor_formatting"
    TOO_VERBOSE = "too_verbose"
    TOO_BRIEF = "too_brief"
    
    # Other
    OTHER = "other"


class FeedbackRequest(BaseModel):
    
    # Link to the query
    request_id: UUID = Field(
        ...,
        description="The request_id from the original query response",
    )
    
    # Simple rating
    rating: FeedbackRating = Field(
        ...,
        description="Overall rating: positive or negative",
    )
    
    # Optional detailed feedback
    category: FeedbackCategory | None = Field(
        default=None,
        description="Category of feedback for negative ratings",
    )
    
    comment: str | None = Field(
        default=None,
        max_length=1000,
        description="Optional free-text comment",
    )
    
    # Specific feedback on sources
    source_feedback: list[dict[str, Any]] | None = Field(
        default=None,
        description="Feedback on individual sources (e.g., which were relevant)",
    )
    
    # Expected response (for training)
    expected_response: str | None = Field(
        default=None,
        description="What the user expected as a response",
    )


class FeedbackRecord(BaseModel):
    
    # Identification
    feedback_id: UUID = Field(default_factory=uuid4)
    request_id: UUID
    
    # User context
    user_id: str
    user_role: str
    
    # Original query context
    query: str
    task_type: str
    
    # Feedback content
    rating: FeedbackRating
    category: FeedbackCategory | None = None
    comment: str | None = None
    
    # Source tracking
    sources_used: list[str] = Field(default_factory=list)
    source_feedback: list[dict[str, Any]] | None = None
    
    # Expected response
    expected_response: str | None = None
    
    # Response metadata
    response_preview: str | None = None
    confidence_score: float | None = None
    
    # Retrieval metadata (for debugging)
    retrieval_scores: list[float] = Field(default_factory=list)
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    query_timestamp: datetime | None = None
    
    def to_analysis_dict(self) -> dict[str, Any]:
        return {
            "feedback_id": str(self.feedback_id),
            "request_id": str(self.request_id),
            "user_id": self.user_id,
            "user_role": self.user_role,
            "query": self.query,
            "task_type": self.task_type,
            "rating": self.rating.value,
            "category": self.category.value if self.category else None,
            "comment": self.comment,
            "sources_count": len(self.sources_used),
            "created_at": self.created_at.isoformat(),
        }


class FeedbackResponse(BaseModel):
    
    feedback_id: UUID
    status: str = "recorded"
    message: str = "Thank you for your feedback"


class FeedbackStats(BaseModel):
    
    # Time range
    period_start: datetime
    period_end: datetime
    
    # Counts
    total_feedback: int
    positive_count: int
    negative_count: int
    
    # Rates
    positive_rate: float
    negative_rate: float
    
    # Breakdown by task type
    by_task_type: dict[str, dict[str, int]] = Field(default_factory=dict)
    
    # Breakdown by category (for negative)
    by_category: dict[str, int] = Field(default_factory=dict)
    
    # Common issues
    common_issues: list[str] = Field(default_factory=list)
