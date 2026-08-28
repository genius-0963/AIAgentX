"""Audit API schemas."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from app.application.services.audit_logger import AuditEntry, AuditEventType


@dataclass(frozen=True, slots=True)
class AuditLogEntry:
    id: UUID
    timestamp: datetime
    tenant_id: UUID
    run_id: UUID | None
    agent_version_id: UUID | None
    event_type: AuditEventType
    tool_name: str | None
    action: str | None
    resource: str | None
    input_data: dict[str, Any] | None
    output_data: dict[str, Any] | None
    success: bool
    reason: str
    metadata: dict[str, Any]
    approval_id: UUID | None
    user_id: str | None

    @classmethod
    def from_entity(cls, entry: AuditEntry) -> "AuditLogEntry":
        return cls(
            id=entry.id,
            timestamp=entry.timestamp,
            tenant_id=entry.tenant_id,
            run_id=entry.run_id,
            agent_version_id=entry.agent_version_id,
            event_type=entry.event_type,
            tool_name=entry.tool_name,
            action=entry.action,
            resource=entry.resource,
            input_data=entry.input_data,
            output_data=entry.output_data,
            success=entry.success,
            reason=entry.reason,
            metadata=entry.metadata,
            approval_id=entry.approval_id,
            user_id=entry.user_id,
        )


@dataclass(frozen=True, slots=True)
class AuditLogListResponse:
    entries: list[AuditLogEntry]
    total: int


@dataclass(frozen=True, slots=True)
class AuditStatsResponse:
    total_events: int
    by_event_type: dict[str, int]
    by_tool: dict[str, int]
    approval_rate: float
    denial_rate: float
    rate_limit_hits: int