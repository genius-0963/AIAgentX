"""Memory API schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.domain.entities.memory import AllowedUseLabel, MemoryScope


class MemoryWriteRequest(BaseModel):
    """Request to write memory."""

    content: str = Field(..., min_length=1, max_length=100000)
    scope: MemoryScope = Field(..., description="Memory scope: ephemeral, session, or durable")
    namespace: str = Field(..., min_length=1, max_length=100, pattern=r"^[a-zA-Z0-9_-]+$")
    metadata: dict[str, Any] = Field(default_factory=dict)
    session_id: str | None = Field(None, max_length=255)


class MemoryWriteResponse(BaseModel):
    """Response for memory write."""

    records: list[MemoryRecordResponse]
    chunk_count: int
    was_redacted: bool


class MemoryRecordResponse(BaseModel):
    """Memory record in API response."""

    id: UUID
    tenant_id: UUID
    agent_id: UUID
    scope: MemoryScope
    namespace: str
    content: str
    metadata: dict[str, Any]
    allowed_use_label: AllowedUseLabel
    session_id: str | None
    expires_at: datetime | None
    created_at: datetime
    updated_at: datetime
    similarity: float | None = None


class MemorySearchRequest(BaseModel):
    """Request to search memory."""

    query: str = Field(..., min_length=1, max_length=1000)
    scope: MemoryScope
    namespace: str = Field(..., min_length=1, max_length=100, pattern=r"^[a-zA-Z0-9_-]+$")
    limit: int = Field(8, ge=1, le=50)
    session_id: str | None = Field(None, max_length=255)
    metadata_filters: dict[str, Any] = Field(default_factory=dict)
    similarity_threshold: float = Field(0.7, ge=0.0, le=1.0)


class MemorySearchResponse(BaseModel):
    """Response for memory search."""

    results: list[MemoryRecordResponse]
    query: str
    total_found: int
    limit: int


class MemoryListRequest(BaseModel):
    """Request to list memory records."""

    limit: int = Field(100, ge=1, le=100)
    offset: int = Field(0, ge=0)


class MemoryListResponse(BaseModel):
    """Response for memory list."""

    records: list[MemoryRecordResponse]
    limit: int
    offset: int
    total: int


class SessionCreateRequest(BaseModel):
    """Request to create a session."""

    session_id: str = Field(..., min_length=1, max_length=255)
    metadata: dict[str, Any] = Field(default_factory=dict)


class SessionCreateResponse(BaseModel):
    """Response for session creation."""

    session_id: str
    tenant_id: UUID
    agent_id: UUID
    created_at: datetime
    message_count: int
    metadata: dict[str, Any]


class SessionAddRequest(BaseModel):
    """Request to add message to session."""

    role: str = Field(..., pattern=r"^(user|assistant|system)$")
    content: str = Field(..., min_length=1, max_length=50000)
    metadata: dict[str, Any] = Field(default_factory=dict)


class SessionAddResponse(BaseModel):
    """Response for adding to session."""

    session_id: str
    message_count: int
    updated_at: datetime


class SessionContextResponse(BaseModel):
    """Response for session context."""

    session_id: str
    messages: list[dict[str, Any]]
    message_count: int


class SessionEndResponse(BaseModel):
    """Response for ending session."""

    session_id: str
    ended_at: datetime
    summarized: bool
    summary_id: UUID | None
    final_message_count: int


class SessionListResponse(BaseModel):
    """Response for listing sessions."""

    sessions: list[dict[str, Any]]
    limit: int
    offset: int
    total: int


class MemoryStatsResponse(BaseModel):
    """Response for memory statistics."""

    tenant_id: UUID
    scopes: dict[str, dict[str, Any]]
    total_records: int
    total_storage_mb: float
    retention_policies: list[dict[str, Any]]


class RetentionPolicyRequest(BaseModel):
    """Request to create/update retention policy."""

    scope: MemoryScope
    retention_days: int = Field(..., ge=1, le=3650)
    max_records_per_tenant: int | None = Field(None, ge=1)
    max_storage_mb: int | None = Field(None, ge=1)


class RetentionPolicyResponse(BaseModel):
    """Response for retention policy."""

    id: UUID
    tenant_id: UUID
    scope: MemoryScope
    retention_days: int
    max_records_per_tenant: int | None
    max_storage_mb: int | None
    created_at: datetime
    updated_at: datetime


class CleanupRequest(BaseModel):
    """Request to run cleanup."""

    enforce_retention: bool = True
    check_quotas: bool = True


class CleanupResponse(BaseModel):
    """Response for cleanup operation."""

    tenant_id: UUID
    expired_cleanup: dict[str, Any]
    retention_enforcement: list[dict[str, Any]]
    quota_status: list[dict[str, Any]]
    total_duration_ms: float