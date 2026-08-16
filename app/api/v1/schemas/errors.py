"""RFC 7807 compliant error response schemas."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class ErrorDetail(BaseModel):
    """Detailed error information following RFC 7807."""

    type: str = Field(
        ...,
        description="A URI reference that identifies the problem type",
        examples=["https://api.aiagentx.com/errors/validation-error"],
    )
    title: str = Field(
        ...,
        description="A short, human-readable summary of the problem type",
        examples=["Validation Error"],
    )
    status: int = Field(
        ...,
        description="The HTTP status code",
        examples=[400],
    )
    detail: str = Field(
        ...,
        description="A human-readable explanation specific to this occurrence",
        examples=["max_steps must be between 1 and 50"],
    )
    request_id: str = Field(
        ...,
        description="Unique identifier for the request",
        examples=["req_abc123"],
    )
    code: str = Field(
        ...,
        description="Application-specific error code",
        examples=["VALIDATION_ERROR"],
    )
    extra: dict[str, Any] | None = Field(
        default=None,
        description="Additional error context",
    )


class ErrorResponse(BaseModel):
    """Standard error response wrapper."""

    error: ErrorDetail

    class Config:
        json_schema_extra = {
            "example": {
                "error": {
                    "type": "https://api.aiagentx.com/errors/validation-error",
                    "title": "Validation Error",
                    "status": 400,
                    "detail": "max_steps must be between 1 and 50",
                    "request_id": "req_abc123",
                    "code": "VALIDATION_ERROR",
                }
            }
        }
