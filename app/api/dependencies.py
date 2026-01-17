
from typing import Annotated

from fastapi import Depends

from app.core.security import User, get_current_user
from app.retrieval.hybrid import HybridRetriever, get_hybrid_retriever
from app.retrieval.vector_store import VectorStore, get_vector_store
from app.services.feedback import FeedbackService, get_feedback_service
from app.services.llm import LLMService, get_llm_service
from app.workflows.orchestrator import WorkflowOrchestrator, get_orchestrator

# Type aliases for cleaner route signatures
CurrentUser = Annotated[User, Depends(get_current_user)]
Orchestrator = Annotated[WorkflowOrchestrator, Depends(get_orchestrator)]
Retriever = Annotated[HybridRetriever, Depends(get_hybrid_retriever)]
LLM = Annotated[LLMService, Depends(get_llm_service)]
Feedback = Annotated[FeedbackService, Depends(get_feedback_service)]
VectorDB = Annotated[VectorStore, Depends(get_vector_store)]
