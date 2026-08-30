from typing import Any, Optional
from fastapi import HTTPException, status


class AppError(HTTPException):
    def __init__(
        self,
        status_code: int,
        error_code: str,
        message: str,
        details: Optional[Any] = None,
    ):
        super().__init__(
            status_code=status_code,
            detail={
                "error_code": error_code,
                "message": message,
                "details": details or {},
            },
        )


class AuthRequiredError(AppError):
    def __init__(self, message: str = "Authentication required"):
        super().__init__(status.HTTP_401_UNAUTHORIZED, "AUTH_REQUIRED", message)


class ForbiddenError(AppError):
    def __init__(self, message: str = "Insufficient permissions to perform this action"):
        super().__init__(status.HTTP_403_FORBIDDEN, "FORBIDDEN", message)


class DocumentInvalidError(AppError):
    def __init__(self, message: str = "Document is invalid, corrupt, or unsupported", details: Any = None):
        super().__init__(status.HTTP_400_BAD_REQUEST, "DOCUMENT_INVALID", message, details)


class IngestionFailedError(AppError):
    def __init__(self, message: str = "Document ingestion pipeline failed", details: Any = None):
        super().__init__(status.HTTP_500_INTERNAL_SERVER_ERROR, "INGESTION_FAILED", message, details)


class NoRelevantContextError(AppError):
    def __init__(self, message: str = "No sufficiently relevant college documents found to answer this question"):
        super().__init__(status.HTTP_404_NOT_FOUND, "NO_RELEVANT_CONTEXT", message)


class ConflictingSourcesError(AppError):
    def __init__(self, message: str = "Conflicting document sources detected", details: Any = None):
        super().__init__(status.HTTP_409_CONFLICT, "CONFLICTING_SOURCES", message, details)


class LLMUnavailableError(AppError):
    def __init__(self, message: str = "LLM generation provider is unavailable"):
        super().__init__(status.HTTP_503_SERVICE_UNAVAILABLE, "LLM_UNAVAILABLE", message)


class RateLimitedError(AppError):
    def __init__(self, message: str = "Rate limit exceeded. Please retry shortly."):
        super().__init__(status.HTTP_429_TOO_MANY_REQUESTS, "RATE_LIMITED", message)


class InternalError(AppError):
    def __init__(self, message: str = "An unexpected error occurred", details: Any = None):
        super().__init__(status.HTTP_500_INTERNAL_SERVER_ERROR, "INTERNAL_ERROR", message, details)
