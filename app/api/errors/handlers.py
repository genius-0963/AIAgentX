"""FastAPI exception handlers for RFC 7807 compliant error responses."""

from __future__ import annotations

from typing import Any

from fastapi import Request, status
from fastapi.responses import JSONResponse
from pydantic import ValidationError as PydanticValidationError

from app.api.errors.exceptions import (
    APIError,
    ConflictError,
    NotFoundError,
    PayloadTooLargeError,
    RateLimitExceededError,
    ValidationError,
)
from app.api.v1.schemas.errors import ErrorDetail


def create_error_response(
    request: Request,
    status_code: int,
    title: str,
    detail: str,
    code: str,
    error_type: str | None = None,
    extra: dict[str, Any] | None = None,
) -> JSONResponse:
    """Create a standardized RFC 7807 error response.

    Args:
        request: The FastAPI request object
        status_code: HTTP status code
        title: Short, human-readable summary
        detail: Human-readable explanation
        code: Application-specific error code
        error_type: URI reference for error type
        extra: Additional error context

    Returns:
        JSONResponse with RFC 7807 compliant error format
    """
    request_id = getattr(request.state, "request_id", "unknown")
    error_type = error_type or f"https://api.aiagentx.com/errors/{code.lower()}"

    error_detail = ErrorDetail(
        type=error_type,
        title=title,
        status=status_code,
        detail=detail,
        request_id=request_id,
        code=code,
        extra=extra,
    )

    return JSONResponse(
        status_code=status_code,
        content={"error": error_detail.model_dump()},
    )


async def api_error_handler(request: Request, exc: APIError) -> JSONResponse:
    """Handle base APIError exceptions.

    Args:
        request: The FastAPI request object
        exc: The APIError exception

    Returns:
        JSONResponse with error details
    """
    return create_error_response(
        request=request,
        status_code=exc.status_code,
        title=exc.error_code.replace("_", " ").title(),
        detail=exc.message,
        code=exc.error_code,
        error_type=exc.error_type,
        extra=exc.extra,
    )


async def validation_error_handler(request: Request, exc: ValidationError) -> JSONResponse:
    """Handle ValidationError exceptions.

    Args:
        request: The FastAPI request object
        exc: The ValidationError exception

    Returns:
        JSONResponse with validation error details
    """
    return create_error_response(
        request=request,
        status_code=exc.status_code,
        title="Validation Error",
        detail=exc.message,
        code=exc.error_code,
        extra=exc.extra,
    )


async def not_found_error_handler(request: Request, exc: NotFoundError) -> JSONResponse:
    """Handle NotFoundError exceptions.

    Args:
        request: The FastAPI request object
        exc: The NotFoundError exception

    Returns:
        JSONResponse with not found error details
    """
    return create_error_response(
        request=request,
        status_code=exc.status_code,
        title="Resource Not Found",
        detail=exc.message,
        code=exc.error_code,
        extra=exc.extra,
    )


async def conflict_error_handler(request: Request, exc: ConflictError) -> JSONResponse:
    """Handle ConflictError exceptions.

    Args:
        request: The FastAPI request object
        exc: The ConflictError exception

    Returns:
        JSONResponse with conflict error details
    """
    return create_error_response(
        request=request,
        status_code=exc.status_code,
        title="Conflict",
        detail=exc.message,
        code=exc.error_code,
        extra=exc.extra,
    )


async def pydantic_validation_error_handler(
    request: Request,
    exc: PydanticValidationError,
) -> JSONResponse:
    """Handle Pydantic validation errors.

    Args:
        request: The FastAPI request object
        exc: The PydanticValidationError exception

    Returns:
        JSONResponse with validation error details
    """
    errors = exc.errors()
    detail = "Validation failed for one or more fields"
    if errors:
        first_error = errors[0]
        field = ".".join(str(loc) for loc in first_error["loc"])
        detail = f"Validation failed for field '{field}': {first_error['msg']}"

    return create_error_response(
        request=request,
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        title="Validation Error",
        detail=detail,
        code="VALIDATION_ERROR",
        extra={"errors": errors},
    )


async def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceededError) -> JSONResponse:
    """Handle RateLimitExceededError exceptions.

    Args:
        request: The FastAPI request object
        exc: The RateLimitExceededError exception

    Returns:
        JSONResponse with rate limit error details
    """
    headers = {}
    if exc.extra and "retry_after" in exc.extra:
        headers["Retry-After"] = str(exc.extra["retry_after"])

    return create_error_response(
        request=request,
        status_code=exc.status_code,
        title="Rate Limit Exceeded",
        detail=exc.message,
        code=exc.error_code,
        extra=exc.extra,
    )


async def payload_too_large_handler(request: Request, exc: PayloadTooLargeError) -> JSONResponse:
    """Handle PayloadTooLargeError exceptions.

    Args:
        request: The FastAPI request object
        exc: The PayloadTooLargeError exception

    Returns:
        JSONResponse with payload too large error details
    """
    return create_error_response(
        request=request,
        status_code=exc.status_code,
        title="Payload Too Large",
        detail=exc.message,
        code=exc.error_code,
        extra=exc.extra,
    )
