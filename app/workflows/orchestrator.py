
import json
import time
from typing import Any

from pydantic import ValidationError

from app.core.config import settings
from app.core.exceptions import (
    IntentDetectionError,
    LLMResponseParseError,
    NoRelevantDocumentsError,
)
from app.core.logging import get_logger
from app.core.security import User, UserRole
from app.models.outputs import get_output_model
from app.models.queries import (
    QueryMetrics,
    QueryRequest,
    QueryResponse,
    SourceDocument,
    TaskType,
)
from app.retrieval.hybrid import HybridRetriever, get_hybrid_retriever
from app.services.llm import LLMService, get_llm_service
from app.workflows.intent import IntentDetector
from app.workflows.prompts import PromptBuilder, get_prompt_builder

logger = get_logger(__name__)


class WorkflowOrchestrator:
    
    def __init__(
        self,
        retriever: HybridRetriever | None = None,
        llm_service: LLMService | None = None,
        prompt_builder: PromptBuilder | None = None,
    ) -> None:
        self.retriever = retriever or get_hybrid_retriever()
        self.llm_service = llm_service or get_llm_service()
        self.prompt_builder = prompt_builder or get_prompt_builder()
        self.intent_detector = IntentDetector(llm_service=self.llm_service)
    
    async def process_query(
        self,
        request: QueryRequest,
        user: User,
    ) -> QueryResponse:
        start_time = time.time()
        
        logger.info(
            "Processing query",
            request_id=str(request.request_id),
            user_id=user.user_id,
            user_role=user.role.value,
        )
        
        try:
            # Step 1: Detect intent (or use provided task_type)
            intent_start = time.time()
            task_type = request.task_type
            intent_confidence = 1.0
            
            if task_type is None:
                intent_match = await self.intent_detector.detect(request.query)
                task_type = intent_match.task_type
                intent_confidence = intent_match.confidence
                
                logger.info(
                    "Intent detected",
                    task_type=task_type.value,
                    confidence=intent_confidence,
                    method=intent_match.method,
                )
            
            # Step 2: Retrieve relevant documents
            retrieval_start = time.time()
            
            documents, context = await self.retriever.retrieve_for_context(
                query=request.query,
                user_role=user.role,
                max_tokens=4000,
                client_name=request.client_name,
                practice_area=request.practice_area,
                document_types=request.document_types,
            )
            
            retrieval_time = int((time.time() - retrieval_start) * 1000)
            
            if not documents:
                logger.warning(
                    "No relevant documents found",
                    query=request.query,
                )
                # Continue with empty context - LLM will indicate lack of sources
                context = "No relevant documents were found for this query."
            
            logger.info(
                "Documents retrieved",
                count=len(documents),
                retrieval_time_ms=retrieval_time,
            )
            
            # Step 3: Build prompt
            system_prompt, user_prompt = self.prompt_builder.build(
                task_type=task_type,
                query=request.query,
                context=context,
                user_role=user.role.value,
                client_name=request.client_name,
            )
            
            # Step 4: Generate response
            generation_start = time.time()
            
            raw_response = await self.llm_service.generate(
                prompt=user_prompt,
                system_prompt=system_prompt,
                temperature=settings.llm_temperature,
                max_tokens=settings.llm_max_tokens,
            )
            
            generation_time = int((time.time() - generation_start) * 1000)
            
            logger.debug(
                "LLM response generated",
                generation_time_ms=generation_time,
                response_length=len(raw_response),
            )
            
            # Step 5: Parse and validate response
            parsed_response = await self._parse_response(
                raw_response=raw_response,
                task_type=task_type,
            )
            
            # Step 6: Build source citations
            sources = [
                SourceDocument(
                    document_id=doc.document_id,
                    filename=doc.filename,
                    title=doc.title,
                    document_type=doc.document_type,
                    section=doc.section_title,
                    relevance_score=doc.score,
                    excerpt=doc.content[:200] + "..." if len(doc.content) > 200 else doc.content,
                )
                for doc in documents[:request.max_sources]
            ] if request.include_sources else []
            
            # Calculate metrics
            total_time = int((time.time() - start_time) * 1000)
            
            metrics = QueryMetrics(
                total_time_ms=total_time,
                retrieval_time_ms=retrieval_time,
                generation_time_ms=generation_time,
                documents_retrieved=len(documents),
                documents_used=len(sources),
                intent_detected=task_type.value,
                intent_confidence=intent_confidence,
            )
            
            logger.info(
                "Query processed successfully",
                request_id=str(request.request_id),
                task_type=task_type.value,
                total_time_ms=total_time,
            )
            
            return QueryResponse(
                request_id=request.request_id,
                success=True,
                response=parsed_response,
                task_type=task_type,
                query=request.query,
                sources=sources,
                confidence=intent_confidence,
                metrics=metrics,
                user_role=user.role.value,
            )
            
        except Exception as e:
            logger.error(
                "Query processing failed",
                request_id=str(request.request_id),
                error=str(e),
                exc_info=True,
            )
            
            total_time = int((time.time() - start_time) * 1000)
            
            return QueryResponse(
                request_id=request.request_id,
                success=False,
                error=str(e),
                response={},
                task_type=task_type or TaskType.QUESTION_ANSWER,
                query=request.query,
                metrics=QueryMetrics(
                    total_time_ms=total_time,
                    retrieval_time_ms=0,
                    generation_time_ms=0,
                    documents_retrieved=0,
                    documents_used=0,
                ),
                user_role=user.role.value,
            )
    
    async def _parse_response(
        self,
        raw_response: str,
        task_type: TaskType,
    ) -> dict[str, Any]:
        if not settings.feature_structured_output_enabled:
            return {"raw_response": raw_response}
        
        # Clean up response
        cleaned = raw_response.strip()
        
        # Remove markdown code blocks if present
        if cleaned.startswith("```"):
            # Find the end of the opening fence
            first_newline = cleaned.find("\n")
            # Find the closing fence
            last_fence = cleaned.rfind("```")
            if last_fence > first_newline:
                cleaned = cleaned[first_newline + 1:last_fence].strip()
        
        # Try to parse JSON
        try:
            parsed = json.loads(cleaned)
            
            # Validate against expected schema
            output_model = get_output_model(task_type.value)
            validated = output_model.model_validate(parsed)
            
            return validated.model_dump()
            
        except json.JSONDecodeError as e:
            logger.warning(
                "JSON parse error",
                error=str(e),
                response_preview=cleaned[:200],
            )
            
            # Try to extract JSON from response
            try:
                import re
                json_match = re.search(r"\{[\s\S]*\}", cleaned)
                if json_match:
                    parsed = json.loads(json_match.group())
                    return parsed
            except Exception:
                pass
            
            # Return as narrative response
            return {
                "summary": cleaned[:500],
                "raw_response": cleaned,
                "parse_error": str(e),
            }
            
        except ValidationError as e:
            logger.warning(
                "Response validation error",
                error=str(e),
            )
            
            # Return parsed JSON even if it doesn't match schema
            try:
                return json.loads(cleaned)
            except Exception:
                return {
                    "summary": cleaned[:500],
                    "validation_error": str(e),
                }


# Singleton instance
_orchestrator: WorkflowOrchestrator | None = None


def get_orchestrator() -> WorkflowOrchestrator:
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = WorkflowOrchestrator()
    return _orchestrator
