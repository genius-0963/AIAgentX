"""Audit log domain entity."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4


class AuditEventType(StrEnum):
    """Types of audit events."""

    TOOL_EXECUTED = "tool_executed"
    TOOL_DENIED = "tool_denied"
    APPROVAL_REQUESTED = "approval_requested"
    APPROVAL_GRANTED = "approval_granted"
    APPROVAL_DENIED = "approval_denied"
    RATE_LIMITED = "rate_limited"
    POLICY_VIOLATION = "policy_violation"
    AUTHENTICATION_FAILED = "authentication_failed"
    AUTHORIZATION_FAILED = "authorization_failed"
    DATA_ACCESS = "data_access"
    CONFIG_CHANGED = "config_changed"


@dataclass(frozen=True, slots=True)
class AuditLogEntry:
    """Audit log entry entity."""

    tenant_id: UUID
    run_id: UUID | None = None
    agent_version_id: UUID | None = None
    event_type: AuditEventType = AuditEventType.TOOL_EXECUTED
    tool_name: str | None = None
    action: str | None = None
    resource: str | None = None
    input_data: dict[str, Any] = field(default_factory=dict)
    output_data: dict[str, Any] = field(default_factory=dict)
    success: bool = True
    reason: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    approval_id: UUID | None = None
    user_id: str | None = None
    id: UUID = field(default_factory=uuid4)
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))