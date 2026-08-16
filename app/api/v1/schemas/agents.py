"""Agent-related API request and response schemas."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.domain.entities.agent import AgentStatus


class AgentCreate(BaseModel):
    """Schema for creating a new agent."""

    name: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Agent name",
        examples=["Research Assistant"],
    )
    description: str | None = Field(
        None,
        max_length=1000,
        description="Optional agent description",
        examples=["Helps with research tasks"],
    )

    @field_validator("name")
    @classmethod
    def name_must_not_be_whitespace(cls, value: str) -> str:
        """Ensure name is not just whitespace."""
        if not value.strip():
            raise ValueError("Agent name cannot be empty or whitespace")
        return value.strip()


class AgentUpdate(BaseModel):
    """Schema for updating an existing agent."""

    name: str | None = Field(
        None,
        min_length=1,
        max_length=200,
        description="Updated agent name",
        examples=["Research Assistant v2"],
    )
    description: str | None = Field(
        None,
        max_length=1000,
        description="Updated agent description",
        examples=["Enhanced research assistant with better capabilities"],
    )

    @field_validator("name")
    @classmethod
    def name_must_not_be_whitespace(cls, value: str | None) -> str | None:
        """Ensure name is not just whitespace if provided."""
        if value is not None and not value.strip():
            raise ValueError("Agent name cannot be empty or whitespace")
        return value.strip() if value else None


class AgentVersionCreate(BaseModel):
    """Schema for creating a new agent version."""

    version: int = Field(
        ...,
        gt=0,
        description="Version number (must be positive)",
        examples=[1],
    )
    system_prompt: str = Field(
        ...,
        min_length=1,
        description="System prompt for the agent",
        examples=["You are a helpful research assistant."],
    )
    model_policy: dict[str, Any] = Field(
        ...,
        description="Model configuration policy",
        examples=[{"model": "gpt-4", "temperature": 0.7, "max_tokens": 2000}],
    )
    memory_mode: str = Field(
        ...,
        description="Memory mode for the agent",
        examples=["ephemeral"],
    )

    @field_validator("system_prompt")
    @classmethod
    def system_prompt_must_not_be_whitespace(cls, value: str) -> str:
        """Ensure system prompt is not just whitespace."""
        if not value.strip():
            raise ValueError("System prompt cannot be empty or whitespace")
        return value


class AgentVersionUpdate(BaseModel):
    """Schema for updating a draft agent version."""

    system_prompt: str | None = Field(
        None,
        min_length=1,
        description="Updated system prompt",
        examples=["You are an enhanced research assistant."],
    )
    model_policy: dict[str, Any] | None = Field(
        None,
        description="Updated model configuration policy",
        examples=[{"model": "gpt-4-turbo", "temperature": 0.5, "max_tokens": 4000}],
    )
    memory_mode: str | None = Field(
        None,
        description="Updated memory mode",
        examples=["session"],
    )

    @field_validator("system_prompt")
    @classmethod
    def system_prompt_must_not_be_whitespace(cls, value: str | None) -> str | None:
        """Ensure system prompt is not just whitespace if provided."""
        if value is not None and not value.strip():
            raise ValueError("System prompt cannot be empty or whitespace")
        return value


class ToolGrantCreate(BaseModel):
    """Schema for creating a tool grant."""

    tool_name: str = Field(
        ...,
        min_length=1,
        description="Name of the tool to grant access to",
        examples=["web_search"],
    )
    policy: dict[str, Any] = Field(
        ...,
        description="Access policy for the tool",
        examples=[{"max_results": 10, "allowed_domains": ["*.edu"]}],
    )


class ToolGrantResponse(BaseModel):
    """Schema for tool grant response."""

    id: UUID = Field(..., description="Tool grant ID")
    tool_name: str = Field(..., description="Tool name")
    policy: dict[str, Any] = Field(..., description="Access policy")
    created_at: str = Field(..., description="Creation timestamp (ISO 8601)")

    class Config:
        from_attributes = True


class AgentVersionResponse(BaseModel):
    """Schema for agent version response."""

    id: UUID = Field(..., description="Version ID")
    version: int = Field(..., description="Version number")
    system_prompt: str = Field(..., description="System prompt")
    model_policy: dict[str, Any] = Field(..., description="Model configuration")
    memory_mode: str = Field(..., description="Memory mode")
    status: AgentStatus = Field(..., description="Version status")
    tool_grants: list[ToolGrantResponse] = Field(
        default_factory=list,
        description="Tool grants for this version",
    )
    created_at: str = Field(..., description="Creation timestamp (ISO 8601)")
    updated_at: str = Field(..., description="Last update timestamp (ISO 8601)")

    class Config:
        from_attributes = True


class AgentResponse(BaseModel):
    """Schema for agent response."""

    id: UUID = Field(..., description="Agent ID")
    tenant_id: UUID = Field(..., description="Tenant ID")
    name: str = Field(..., description="Agent name")
    description: str | None = Field(None, description="Agent description")
    versions: list[AgentVersionResponse] = Field(
        default_factory=list,
        description="Agent versions",
    )
    created_at: str = Field(..., description="Creation timestamp (ISO 8601)")
    updated_at: str = Field(..., description="Last update timestamp (ISO 8601)")

    class Config:
        from_attributes = True
