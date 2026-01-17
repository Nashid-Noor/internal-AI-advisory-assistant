
from fastapi import APIRouter, HTTPException, status

from app.api.dependencies import CurrentUser, Orchestrator
from app.core.logging import LogContext, get_logger
from app.models.queries import QueryRequest, QueryResponse, TaskType

logger = get_logger(__name__)

router = APIRouter(prefix="/query", tags=["Query"])


@router.post(
    "",
    response_model=QueryResponse,
    summary="Process an advisory query",
    description="""
    Submit a query to the advisory assistant.
    
    The system will:
    1. Detect the intent (or use provided task_type)
    2. Retrieve relevant documents
    3. Generate a structured response
    
    **Task Types:**
    - `question_answer` - General Q&A
    - `summarize_client` - Client summary
    - `risk_analysis` - Risk identification
    - `draft_recommendations` - Generate recommendations
    - `executive_summary` - High-level briefing
    - `talking_points` - Meeting preparation
    - `action_items` - Extract action items
    - `compare_approaches` - Compare options
    - `research_topic` - Topic research
    
    **Filters:**
    - `client_name` - Filter to specific client
    - `practice_area` - Filter by practice area
    - `document_types` - Filter by document type
    """,
)
async def process_query(
    request: QueryRequest,
    user: CurrentUser,
    orchestrator: Orchestrator,
) -> QueryResponse:
    async with LogContext(
        request_id=str(request.request_id),
        user_id=user.user_id,
        user_role=user.role.value,
    ):
        logger.info(
            "Query received",
            query_preview=request.query[:100],
            task_type=request.task_type.value if request.task_type else "auto-detect",
        )
        
        response = await orchestrator.process_query(
            request=request,
            user=user,
        )
        
        if not response.success:
            logger.warning(
                "Query failed",
                error=response.error,
            )
        
        return response


@router.get(
    "/task-types",
    summary="List available task types",
    description="Get all supported task types with descriptions",
)
async def list_task_types() -> dict[str, list[dict[str, str]]]:
    task_descriptions = {
        TaskType.QUESTION_ANSWER: "Answer a general question",
        TaskType.SUMMARIZE_CLIENT: "Summarize client background",
        TaskType.CLIENT_BACKGROUND: "Get client background information",
        TaskType.RISK_ANALYSIS: "Identify and analyze risks",
        TaskType.OPPORTUNITY_ANALYSIS: "Identify opportunities",
        TaskType.DRAFT_RECOMMENDATIONS: "Generate recommendations",
        TaskType.ACTION_ITEMS: "Extract action items",
        TaskType.EXECUTIVE_SUMMARY: "Create executive summary",
        TaskType.TALKING_POINTS: "Prepare talking points",
        TaskType.COMPARE_APPROACHES: "Compare options/approaches",
        TaskType.RESEARCH_TOPIC: "Research a topic",
    }
    
    return {
        "task_types": [
            {"type": task.value, "description": desc}
            for task, desc in task_descriptions.items()
        ]
    }
