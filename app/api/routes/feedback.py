
from fastapi import APIRouter, HTTPException, status

from app.api.dependencies import CurrentUser, Feedback
from app.core.logging import get_logger
from app.core.security import UserRole, require_role
from app.models.feedback import (
    FeedbackRequest,
    FeedbackResponse,
    FeedbackStats,
)

logger = get_logger(__name__)

router = APIRouter(prefix="/feedback", tags=["Feedback"])


@router.post(
    "",
    response_model=FeedbackResponse,
    summary="Submit feedback",
    description="""
    Submit feedback on a query response.
    
    **Rating:**
    - `positive` - The response was helpful
    - `negative` - The response was not helpful
    
    **Categories (for negative feedback):**
    - `incorrect_information` - Response contained errors
    - `incomplete_answer` - Response was missing information
    - `irrelevant_response` - Response wasn't relevant to query
    - `wrong_sources` - Sources were not appropriate
    - `missing_sources` - Expected sources were missing
    - `poor_formatting` - Response was poorly formatted
    - `too_verbose` - Response was too long
    - `too_brief` - Response was too short
    """,
)
async def submit_feedback(
    request: FeedbackRequest,
    user: CurrentUser,
    feedback_service: Feedback,
) -> FeedbackResponse:
    logger.info(
        "Feedback received",
        request_id=str(request.request_id),
        rating=request.rating.value,
        user_id=user.user_id,
    )
    
    # Note: In a production system, we would look up the original query
    # from a query log to get additional context. For this implementation,
    # we accept the feedback with minimal context.
    
    return await feedback_service.record_feedback(
        request=request,
        user_id=user.user_id,
        user_role=user.role.value,
        query="",  # Would be retrieved from query log
        task_type="unknown",  # Would be retrieved from query log
    )


@router.get(
    "/stats",
    response_model=FeedbackStats,
    summary="Get feedback statistics",
    description="Get aggregated feedback statistics (requires Partner role)",
)
async def get_feedback_stats(
    user: CurrentUser,
    feedback_service: Feedback,
    days: int = 30,
    task_type: str | None = None,
) -> FeedbackStats:
    # Check role
    if not user.role.can_access(UserRole.PARTNER):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Feedback statistics require Partner role",
        )
    
    return await feedback_service.get_stats(
        days=days,
        task_type=task_type,
    )


@router.get(
    "/export",
    summary="Export feedback data",
    description="Export feedback data for analysis (requires Partner role)",
)
async def export_feedback(
    user: CurrentUser,
    feedback_service: Feedback,
    days: int = 90,
) -> dict:
    if not user.role.can_access(UserRole.PARTNER):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Feedback export requires Partner role",
        )
    
    data = await feedback_service.export_for_analysis(days=days)
    
    return {
        "count": len(data),
        "feedback": data,
    }
