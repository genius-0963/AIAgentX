from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, UTC, timedelta
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from app.domain.entities.base import Entity, AggregateRoot


class ApprovalState(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class ApprovalType(StrEnum):
    TOOL_EXECUTION = "tool_execution"
    SENSITIVE_ACTION = "sensitive_action"
    BUDGET_EXCEED = "budget_exceed"
    POLICY_VIOLATION = "policy_violation"


@dataclass(slots=True, kw_only=True)
class ApprovalRequest(AggregateRoot):
    """Human-in-the-loop approval request."""

    run_id: UUID
    step_sequence: int
    approval_type: ApprovalType
    state: ApprovalState = ApprovalState.PENDING

    tool_name: str
    action: str
    resource: str | None = None
    input_data: dict[str, Any] = field(default_factory=dict)
    policy_reason: str = ""

    requested_by: str = "system"
    requested_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    approved_by: str | None = None
    approved_at: datetime | None = None
    denial_reason: str | None = None

    expires_at: datetime | None = None
    ttl_seconds: int = 3600

    response_data: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        if self.expires_at is None:
            self.expires_at = datetime.now(UTC) + timedelta(seconds=self.ttl_seconds)
        if not self.tool_name or not self.tool_name.strip():
            raise ValueError("Tool name cannot be empty")
        if not self.action or not self.action.strip():
            raise ValueError("Action cannot be empty")

    def approve(self, approved_by: str, response_data: dict[str, Any] | None = None) -> None:
        if self.state != ApprovalState.PENDING:
            raise ValueError(f"Cannot approve request in state {self.state}")
        if self.is_expired():
            raise ValueError("Approval request has expired")

        self.state = ApprovalState.APPROVED
        self.approved_by = approved_by
        self.approved_at = datetime.now(UTC)
        self.response_data = response_data
        self.touch()
        self.add_event(
            ApprovalGranted(
                approval_id=self.id,
                run_id=self.run_id,
                approved_by=approved_by,
                response_data=response_data,
            )
        )

    def deny(self, denied_by: str, reason: str) -> None:
        if self.state != ApprovalState.PENDING:
            raise ValueError(f"Cannot deny request in state {self.state}")

        self.state = ApprovalState.DENIED
        self.approved_by = denied_by
        self.approved_at = datetime.now(UTC)
        self.denial_reason = reason
        self.touch()
        self.add_event(
            ApprovalDenied(
                approval_id=self.id,
                run_id=self.run_id,
                denied_by=denied_by,
                reason=reason,
            )
        )

    def cancel(self, reason: str) -> None:
        if self.state not in {ApprovalState.PENDING, ApprovalState.APPROVED}:
            return
        self.state = ApprovalState.CANCELLED
        self.denial_reason = reason
        self.touch()
        self.add_event(
            ApprovalCancelled(
                approval_id=self.id,
                run_id=self.run_id,
                reason=reason,
            )
        )

    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        return datetime.now(UTC) > self.expires_at


@dataclass(slots=True, kw_only=True)
class ApprovalGranted:
    approval_id: UUID
    run_id: UUID
    approved_by: str
    response_data: dict[str, Any] | None = None


@dataclass(slots=True, kw_only=True)
class ApprovalDenied:
    approval_id: UUID
    run_id: UUID
    denied_by: str
    reason: str


@dataclass(slots=True, kw_only=True)
class ApprovalCancelled:
    approval_id: UUID
    run_id: UUID
    reason: str