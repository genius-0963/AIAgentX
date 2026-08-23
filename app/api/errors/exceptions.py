"""Custom API exception classes following RFC 7807."""

from __future__ import annotations

from typing import Any


class APIError(Exception):
    """Base exception for API errors.

    All custom API exceptions should inherit from this class to ensure
    consistent error handling and RFC 7807 compliance.
    """

    def __init__(
        self,
        message: str,
        status_code: int,
        error_code: str,
        error_type: str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        """Initialize API error.

        Args:
            message: Human-readable error message
            status_code: HTTP status code
            error_code: Application-specific error code
            error_type: URI reference identifying the error type
            extra: Additional error context
        """
        self.message = message
        self.status_code = status_code
        self.error_code = error_code
        self.error_type = error_type or f"https://api.aiagentx.com/errors/{error_code.lower()}"
        self.extra = extra or {}
        super().__init__(self.message)


class ValidationError(APIError):
    """Exception for validation errors (400 Bad Request)."""

    def __init__(
        self,
        message: str,
        field: str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        """Initialize validation error.

        Args:
            message: Validation error message
            field: Field that failed validation (optional)
            extra: Additional error context
        """
        context = extra or {}
        if field:
            context["field"] = field
        super().__init__(
            message=message,
            status_code=400,
            error_code="VALIDATION_ERROR",
            extra=context,
        )


class NotFoundError(APIError):
    """Exception for resource not found errors (404 Not Found)."""

    def __init__(
        self,
        message: str,
        resource_type: str | None = None,
        resource_id: str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        """Initialize not found error.

        Args:
            message: Error message
            resource_type: Type of resource not found (optional)
            resource_id: ID of resource not found (optional)
            extra: Additional error context
        """
        context = extra or {}
        if resource_type:
            context["resource_type"] = resource_type
        if resource_id:
            context["resource_id"] = resource_id
        super().__init__(
            message=message,
            status_code=404,
            error_code="NOT_FOUND",
            extra=context,
        )


class ConflictError(APIError):
    """Exception for conflict errors (409 Conflict)."""

    def __init__(
        self,
        message: str,
        conflict_type: str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        """Initialize conflict error.

        Args:
            message: Error message
            conflict_type: Type of conflict (optional)
            extra: Additional error context
        """
        context = extra or {}
        if conflict_type:
            context["conflict_type"] = conflict_type
        super().__init__(
            message=message,
            status_code=409,
            error_code="CONFLICT",
            extra=context,
        )


class RateLimitExceededError(APIError):
    """Exception for rate limit exceeded errors (429 Too Many Requests)."""

    def __init__(
        self,
        message: str,
        detail: str | None = None,
        retry_after: int | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        """Initialize rate limit exceeded error.

        Args:
            message: Error message
            detail: Detailed error description
            retry_after: Seconds until retry is allowed
            extra: Additional error context
        """
        context = extra or {}
        if detail:
            context["detail"] = detail
        if retry_after is not None:
            context["retry_after"] = retry_after
        super().__init__(
            message=message,
            status_code=429,
            error_code="RATE_LIMIT_EXCEEDED",
            extra=context,
        )


class PayloadTooLargeError(APIError):
    """Exception for payload too large errors (413 Payload Too Large)."""

    def __init__(
        self,
        message: str,
        detail: str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        """Initialize payload too large error.

        Args:
            message: Error message
            detail: Detailed error description
            extra: Additional error context
        """
        context = extra or {}
        if detail:
            context["detail"] = detail
        super().__init__(
            message=message,
            status_code=413,
            error_code="PAYLOAD_TOO_LARGE",
            extra=context,
        )
