"""Audit logging service for tool executions."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, UTC
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4


class AuditEventType(StrEnum):
    TOOL_EXECUTED = "tool_executed"
    TOOL_DENIED = "tool_denied"
    APPROVAL_REQUESTED = "approval_requested"
    APPROVAL_GRANTED = "approval_granted"
    APPROVAL_DENIED = "approval_denied"
    RATE_LIMITED = "rate_limited"
    POLICY_VIOLATION = "policy_violation"


@dataclass(frozen=True, slots=True)
class AuditEntry:
    """Audit log entry."""
    tenant_id: UUID
    event_type: AuditEventType
    success: bool
    reason: str
    id: UUID = field(default_factory=uuid4)
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    run_id: UUID | None = None
    agent_version_id: UUID | None = None
    tool_name: str | None = None
    action: str | None = None
    resource: str | None = None
    input_data: dict[str, Any] | None = None
    output_data: dict[str, Any] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    approval_id: UUID | None = None
    user_id: str | None = None


class AuditRepository:
    """Repository interface for audit logs."""

    async def add(self, entry: AuditEntry) -> None:
        raise NotImplementedError

    async def query(
        self,
        tenant_id: UUID,
        run_id: UUID | None = None,
        event_types: list[AuditEventType] | None = None,
        tool_name: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[AuditEntry]:
        raise NotImplementedError

    async def count(
        self,
        tenant_id: UUID,
        run_id: UUID | None = None,
        event_types: list[AuditEventType] | None = None,
        tool_name: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> int:
        raise NotImplementedError

    async def get_stats(
        self,
        tenant_id: UUID,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> dict[str, Any]:
        raise NotImplementedError


class AuditLogger:
    """Centralized audit logging for tool executions."""

    def __init__(
        self,
        audit_repo: AuditRepository,
    ) -> None:
        self._repo = audit_repo

    async def log(
        self,
        tenant_id: UUID,
        event_type: AuditEventType,
        run_id: UUID | None = None,
        agent_version_id: UUID | None = None,
        tool_name: str | None = None,
        action: str | None = None,
        resource: str | None = None,
        input_data: dict[str, Any] | None = None,
        output_data: dict[str, Any] | None = None,
        success: bool = True,
        reason: str = "",
        metadata: dict[str, Any] | None = None,
        approval_id: UUID | None = None,
        user_id: str | None = None,
    ) -> AuditEntry:
        """Log audit entry."""
        entry = AuditEntry(
            tenant_id=tenant_id,
            run_id=run_id,
            agent_version_id=agent_version_id,
            event_type=event_type,
            tool_name=tool_name,
            action=action,
            resource=resource,
            input_data=input_data,
            output_data=output_data,
            success=success,
            reason=reason,
            metadata=metadata or {},
            approval_id=approval_id,
            user_id=user_id,
        )
        await self._repo.add(entry)
        return entry

    async def query(
        self,
        tenant_id: UUID,
        run_id: UUID | None = None,
        event_types: list[AuditEventType] | None = None,
        tool_name: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[AuditEntry]:
        """Query audit logs."""
        return await self._repo.query(
            tenant_id=tenant_id,
            run_id=run_id,
            event_types=event_types,
            tool_name=tool_name,
            start_time=start_time,
            end_time=end_time,
            limit=limit,
            offset=offset,
        )

    async def get_stats(
        self,
        tenant_id: UUID,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> dict[str, Any]:
        """Get audit statistics."""
        return await self._repo.get_stats(tenant_id, start_time, end_time)