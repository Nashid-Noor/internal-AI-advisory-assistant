
import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import UUID

from app.core.config import settings
from app.core.logging import get_logger
from app.models.feedback import (
    FeedbackCategory,
    FeedbackRating,
    FeedbackRecord,
    FeedbackRequest,
    FeedbackResponse,
    FeedbackStats,
)

logger = get_logger(__name__)


class FeedbackService:
    
    def __init__(self, db_path: str | None = None) -> None:
        self.db_path = db_path or settings.feedback_db_path
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
        logger.info("Feedback service initialized", db_path=self.db_path)
    
    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def _init_db(self) -> None:
        conn = self._get_connection()
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS feedback (
                    feedback_id TEXT PRIMARY KEY,
                    request_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    user_role TEXT NOT NULL,
                    query TEXT NOT NULL,
                    task_type TEXT NOT NULL,
                    rating TEXT NOT NULL,
                    category TEXT,
                    comment TEXT,
                    sources_used TEXT,
                    source_feedback TEXT,
                    expected_response TEXT,
                    response_preview TEXT,
                    confidence_score REAL,
                    retrieval_scores TEXT,
                    created_at TEXT NOT NULL,
                    query_timestamp TEXT
                )
            """)
            
            conn.execute("CREATE INDEX IF NOT EXISTS idx_feedback_rating ON feedback(rating)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_feedback_task_type ON feedback(task_type)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_feedback_created_at ON feedback(created_at)")
            conn.commit()
        finally:
            conn.close()
    
    async def record_feedback(
        self,
        request: FeedbackRequest,
        user_id: str,
        user_role: str,
        query: str,
        task_type: str,
        sources_used: list[str] | None = None,
        response_preview: str | None = None,
        confidence_score: float | None = None,
        retrieval_scores: list[float] | None = None,
        query_timestamp: datetime | None = None,
    ) -> FeedbackResponse:
        record = FeedbackRecord(
            request_id=request.request_id,
            user_id=user_id,
            user_role=user_role,
            query=query,
            task_type=task_type,
            rating=request.rating,
            category=request.category,
            comment=request.comment,
            sources_used=sources_used or [],
            source_feedback=request.source_feedback,
            expected_response=request.expected_response,
            response_preview=response_preview,
            confidence_score=confidence_score,
            retrieval_scores=retrieval_scores or [],
            query_timestamp=query_timestamp,
        )
        
        conn = self._get_connection()
        try:
            conn.execute(
                """
                INSERT INTO feedback (
                    feedback_id, request_id, user_id, user_role,
                    query, task_type, rating, category, comment,
                    sources_used, source_feedback, expected_response,
                    response_preview, confidence_score, retrieval_scores,
                    created_at, query_timestamp
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(record.feedback_id),
                    str(record.request_id),
                    record.user_id,
                    record.user_role,
                    record.query,
                    record.task_type,
                    record.rating.value,
                    record.category.value if record.category else None,
                    record.comment,
                    json.dumps(record.sources_used),
                    json.dumps(record.source_feedback) if record.source_feedback else None,
                    record.expected_response,
                    record.response_preview,
                    record.confidence_score,
                    json.dumps(record.retrieval_scores),
                    record.created_at.isoformat(),
                    record.query_timestamp.isoformat() if record.query_timestamp else None,
                ),
            )
            conn.commit()
            
            logger.info(
                "Feedback recorded",
                feedback_id=str(record.feedback_id),
                rating=record.rating.value,
                task_type=record.task_type,
            )
            
            return FeedbackResponse(
                feedback_id=record.feedback_id,
                status="recorded",
                message="Thank you for your feedback",
            )
            
        except Exception as e:
            logger.error("Failed to record feedback", error=str(e))
            raise
        finally:
            conn.close()
    
    async def get_stats(self, days: int = 30, task_type: str | None = None) -> FeedbackStats:
        period_end = datetime.utcnow()
        period_start = period_end - timedelta(days=days)
        
        conn = self._get_connection()
        try:
            base_where = "WHERE created_at >= ?"
            params: list[Any] = [period_start.isoformat()]
            
            if task_type:
                base_where += " AND task_type = ?"
                params.append(task_type)
            
            cursor = conn.execute(f"SELECT COUNT(*) as total FROM feedback {base_where}", params)
            total = cursor.fetchone()["total"]
            
            cursor = conn.execute(
                f"SELECT COUNT(*) as count FROM feedback {base_where} AND rating = ?",
                params + ["positive"],
            )
            positive = cursor.fetchone()["count"]
            negative = total - positive
            
            cursor = conn.execute(
                f"""
                SELECT task_type, rating, COUNT(*) as count 
                FROM feedback {base_where}
                GROUP BY task_type, rating
                """,
                params,
            )
            
            by_task: dict[str, dict[str, int]] = {}
            for row in cursor:
                task = row["task_type"]
                if task not in by_task:
                    by_task[task] = {"positive": 0, "negative": 0}
                by_task[task][row["rating"]] = row["count"]
            
            cursor = conn.execute(
                f"""
                SELECT category, COUNT(*) as count 
                FROM feedback {base_where} AND category IS NOT NULL
                GROUP BY category
                """,
                params,
            )
            by_category = {row["category"]: row["count"] for row in cursor}
            
            return FeedbackStats(
                period_start=period_start,
                period_end=period_end,
                total_feedback=total,
                positive_count=positive,
                negative_count=negative,
                positive_rate=positive / total if total > 0 else 0,
                negative_rate=negative / total if total > 0 else 0,
                by_task_type=by_task,
                by_category=by_category,
                common_issues=[],
            )
            
        finally:
            conn.close()
    
    async def export_for_analysis(self, days: int = 90) -> list[dict[str, Any]]:
        period_start = datetime.utcnow() - timedelta(days=days)
        
        conn = self._get_connection()
        try:
            cursor = conn.execute(
                "SELECT * FROM feedback WHERE created_at >= ? ORDER BY created_at DESC",
                (period_start.isoformat(),),
            )
            return [dict(row) for row in cursor]
        finally:
            conn.close()


# Singleton instance
_feedback_service: FeedbackService | None = None


def get_feedback_service() -> FeedbackService:
    global _feedback_service
    if _feedback_service is None:
        _feedback_service = FeedbackService()
    return _feedback_service
