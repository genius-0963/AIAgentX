"""Run-related API request and response schemas."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.domain.value_objects.state import RunState


class RunLimits(BaseModel):
    """Schema for run execution limits."""

    max_steps: int = Field(
        ...,
        gt=0,
        le=50,
        description="Maximum number of execution steps",
        examples=[12],
    )
    max_cost_usd: float = Field(
        ...,
        gt=0,
        description="Maximum cost in USD",
        examples=[0.25],
    )
    timeout_seconds: int = Field(
        ...,
        gt=0,
        le=3600,
        description="Maximum execution timeout in seconds",
        examples=[90],
    )


class RunCreate(BaseModel):
    """Schema for creating a new run."""

    input: dict[str, Any] = Field(
        ...,
        description="Input data for the run",
        examples=[{"question": "Summarize this release"}],
    )
    session_id: str | None = Field(
        None,
        description="Optional session ID for conversation continuity",
        examples=["s_456"],
    )
    metadata: dict[str, Any] | None = Field(
        None,
        description="Optional metadata for the run",
        examples=[{"source": "web"}],
    )
    limits: RunLimits = Field(
        ...,
        description="Execution limits for the run",
    )

    @field_validator("input")
    @classmethod
    def input_must_not_be_empty(cls, value: dict[str, Any]) -> dict[str, Any]:
        """Ensure input is not empty."""
        if not value:
            raise ValueError("Input data cannot be empty")
        return value


class RunResponse(BaseModel):
    """Schema for run creation response."""

    id: UUID = Field(..., description="Run ID")
    state: RunState = Field(..., description="Current run state")
    agent_version: int = Field(..., description="Agent version used")
    events_url: str = Field(..., description="URL for SSE events stream")

    class Config:
        json_schema_extra = {
            "example": {
                "id": "run_01J...",
                "state": "queued",
                "agent_version": 3,
                "events_url": "/v1/runs/run_01J.../events",
            }
        }


class UsageSummary(BaseModel):
    """Schema for resource usage summary."""

    steps_completed: int = Field(..., description="Number of completed steps")
    total_cost_usd: float = Field(..., description="Total cost in USD")
    tokens_used: int = Field(..., description="Total tokens used")


class RunStatusResponse(BaseModel):
    """Schema for run status query response."""

    id: UUID = Field(..., description="Run ID")
    tenant_id: UUID = Field(..., description="Tenant ID")
    agent_version_id: UUID = Field(..., description="Agent version ID")
    state: RunState = Field(..., description="Current run state")
    input: dict[str, Any] = Field(..., description="Input data (redacted if sensitive)")
    output: dict[str, Any] | None = Field(None, description="Output data (redacted if sensitive)")
    usage: UsageSummary = Field(..., description="Resource usage summary")
    attempt: int = Field(..., description="Current attempt number")
    max_steps: int = Field(..., description="Maximum steps allowed")
    created_at: str = Field(..., description="Creation timestamp (ISO 8601)")
    updated_at: str = Field(..., description="Last update timestamp (ISO 8601)")
    cancel_requested_at: str | None = Field(
        None,
        description="Cancellation request timestamp (ISO 8601)",
    )

    class Config:
        from_attributes = True
