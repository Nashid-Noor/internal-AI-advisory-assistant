
from datetime import datetime
from typing import Any

from fastapi import APIRouter

from app.core.config import settings
from app.core.logging import get_logger
from app.retrieval.vector_store import get_vector_store
from app.retrieval.bm25 import get_bm25_index

logger = get_logger(__name__)

router = APIRouter(prefix="/health", tags=["Health"])


@router.get(
    "",
    summary="Basic health check",
    description="Simple liveness check",
)
async def health_check() -> dict[str, str]:
    return {"status": "healthy"}


@router.get(
    "/ready",
    summary="Readiness check",
    description="Check if the system is ready to accept requests",
)
async def readiness_check() -> dict[str, Any]:
    status_details: dict[str, Any] = {
        "ready": True,
        "timestamp": datetime.utcnow().isoformat(),
        "components": {},
    }
    
    # Check vector store
    try:
        vector_store = get_vector_store()
        stats = vector_store.get_collection_stats()  # Synchronous
        status_details["components"]["vector_store"] = {
            "status": "healthy",
            "documents": stats.get("points_count", 0),
        }
    except Exception as e:
        status_details["ready"] = False
        status_details["components"]["vector_store"] = {
            "status": "unhealthy",
            "error": str(e),
        }
    
    # Check BM25 index
    try:
        bm25_index = get_bm25_index()
        bm25_stats = bm25_index.get_stats()
        status_details["components"]["bm25_index"] = {
            "status": "healthy",
            "documents": bm25_stats.get("document_count", 0),
        }
    except Exception as e:
        status_details["components"]["bm25_index"] = {
            "status": "unhealthy",
            "error": str(e),
        }
    
    return status_details


@router.get(
    "/info",
    summary="System information",
    description="Get system configuration and version info",
)
async def system_info() -> dict[str, Any]:
    return {
        "app_name": settings.app_name,
        "environment": settings.app_env,
        "version": "0.1.0",
        "features": {
            "hybrid_retrieval": settings.hybrid_enabled,
            "intent_detection": settings.feature_intent_detection_enabled,
            "structured_output": settings.feature_structured_output_enabled,
            "feedback": settings.feature_feedback_enabled,
        },
        "models": {
            "llm": settings.llm_model,
            "embedding": settings.embedding_model,
        },
    }
