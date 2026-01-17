
from typing import Any


class AdvisoryAssistantError(Exception):
    
    error_code: str = "INTERNAL_ERROR"
    status_code: int = 500
    
    def __init__(
        self,
        message: str = "An internal error occurred",
        details: dict[str, Any] | None = None,
    ) -> None:
        self.message = message
        self.details = details or {}
        super().__init__(self.message)
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "error_code": self.error_code,
            "message": self.message,
            "details": self.details,
        }


# =============================================================================
# Authentication & Authorization Errors
# =============================================================================


class AuthenticationError(AdvisoryAssistantError):
    
    error_code = "AUTHENTICATION_FAILED"
    status_code = 401
    
    def __init__(
        self,
        message: str = "Authentication failed",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, details)


class AuthorizationError(AdvisoryAssistantError):
    
    error_code = "AUTHORIZATION_FAILED"
    status_code = 403
    
    def __init__(
        self,
        message: str = "You do not have permission to perform this action",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, details)


class InsufficientRoleError(AuthorizationError):
    
    error_code = "INSUFFICIENT_ROLE"
    
    def __init__(
        self,
        required_role: str,
        user_role: str,
        resource: str | None = None,
    ) -> None:
        details = {
            "required_role": required_role,
            "user_role": user_role,
        }
        if resource:
            details["resource"] = resource
        
        message = f"This action requires '{required_role}' role, but you have '{user_role}'"
        super().__init__(message, details)


# =============================================================================
# Document Processing Errors
# =============================================================================


class DocumentProcessingError(AdvisoryAssistantError):
    
    error_code = "DOCUMENT_PROCESSING_ERROR"
    status_code = 422


class UnsupportedFileTypeError(DocumentProcessingError):
    
    error_code = "UNSUPPORTED_FILE_TYPE"
    
    def __init__(self, file_type: str, supported_types: list[str]) -> None:
        message = f"File type '{file_type}' is not supported"
        details = {
            "file_type": file_type,
            "supported_types": supported_types,
        }
        super().__init__(message, details)


class DocumentParsingError(DocumentProcessingError):
    
    error_code = "DOCUMENT_PARSING_ERROR"
    
    def __init__(self, filename: str, reason: str) -> None:
        message = f"Failed to parse document '{filename}': {reason}"
        details = {
            "filename": filename,
            "reason": reason,
        }
        super().__init__(message, details)


class ChunkingError(DocumentProcessingError):
    
    error_code = "CHUNKING_ERROR"


# =============================================================================
# Retrieval Errors
# =============================================================================


class RetrievalError(AdvisoryAssistantError):
    
    error_code = "RETRIEVAL_ERROR"
    status_code = 500


class VectorStoreError(RetrievalError):
    
    error_code = "VECTOR_STORE_ERROR"
    
    def __init__(self, operation: str, reason: str) -> None:
        message = f"Vector store {operation} failed: {reason}"
        details = {
            "operation": operation,
            "reason": reason,
        }
        super().__init__(message, details)


class EmbeddingError(RetrievalError):
    
    error_code = "EMBEDDING_ERROR"


class NoRelevantDocumentsError(RetrievalError):
    
    error_code = "NO_RELEVANT_DOCUMENTS"
    status_code = 404
    
    def __init__(self, query: str) -> None:
        message = "No relevant documents found for your query"
        details = {"query": query}
        super().__init__(message, details)


# =============================================================================
# LLM Errors
# =============================================================================


class LLMError(AdvisoryAssistantError):
    
    error_code = "LLM_ERROR"
    status_code = 502


class LLMConnectionError(LLMError):
    
    error_code = "LLM_CONNECTION_ERROR"
    
    def __init__(self, provider: str, reason: str) -> None:
        message = f"Failed to connect to LLM provider '{provider}': {reason}"
        details = {
            "provider": provider,
            "reason": reason,
        }
        super().__init__(message, details)


class LLMRateLimitError(LLMError):
    
    error_code = "LLM_RATE_LIMIT"
    status_code = 429
    
    def __init__(self, retry_after: int | None = None) -> None:
        message = "LLM rate limit exceeded. Please try again later."
        details = {}
        if retry_after:
            details["retry_after_seconds"] = retry_after
        super().__init__(message, details)


class LLMResponseParseError(LLMError):
    
    error_code = "LLM_RESPONSE_PARSE_ERROR"
    status_code = 500
    
    def __init__(self, expected_format: str, raw_response: str | None = None) -> None:
        message = f"Failed to parse LLM response into {expected_format} format"
        details = {"expected_format": expected_format}
        if raw_response:
            # Truncate for safety
            details["raw_response_preview"] = raw_response[:200]
        super().__init__(message, details)


# =============================================================================
# Workflow Errors
# =============================================================================


class WorkflowError(AdvisoryAssistantError):
    
    error_code = "WORKFLOW_ERROR"


class UnknownTaskTypeError(WorkflowError):
    
    error_code = "UNKNOWN_TASK_TYPE"
    status_code = 400
    
    def __init__(self, task_type: str, available_tasks: list[str]) -> None:
        message = f"Unknown task type: '{task_type}'"
        details = {
            "task_type": task_type,
            "available_tasks": available_tasks,
        }
        super().__init__(message, details)


class IntentDetectionError(WorkflowError):
    
    error_code = "INTENT_DETECTION_FAILED"
    status_code = 400
    
    def __init__(self, query: str) -> None:
        message = "Could not determine the intent of your query. Please be more specific."
        details = {"query": query}
        super().__init__(message, details)


# =============================================================================
# Validation Errors
# =============================================================================


class ValidationError(AdvisoryAssistantError):
    
    error_code = "VALIDATION_ERROR"
    status_code = 422
    
    def __init__(self, field: str, reason: str) -> None:
        message = f"Validation failed for '{field}': {reason}"
        details = {
            "field": field,
            "reason": reason,
        }
        super().__init__(message, details)


class QueryTooLongError(ValidationError):
    
    error_code = "QUERY_TOO_LONG"
    
    def __init__(self, length: int, max_length: int) -> None:
        super().__init__(
            field="query",
            reason=f"Query length ({length}) exceeds maximum ({max_length})",
        )
        self.details["length"] = length
        self.details["max_length"] = max_length


# =============================================================================
# Rate Limiting Errors
# =============================================================================


class RateLimitError(AdvisoryAssistantError):
    
    error_code = "RATE_LIMIT_EXCEEDED"
    status_code = 429
    
    def __init__(self, retry_after: int) -> None:
        message = f"Rate limit exceeded. Please retry after {retry_after} seconds."
        details = {"retry_after_seconds": retry_after}
        super().__init__(message, details)
