"""Approval API schemas."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from app.domain.entities.approval_request import ApprovalRequest, ApprovalState, ApprovalType


@dataclass(frozen=True, slots=True)
class ApprovalDecisionRequest:
    """Request to approve/deny an approval."""
    response_data: dict[str, Any] | None = None
    denial_reason: str | None = None


@dataclass(frozen=True, slots=True)
class ApprovalResponse:
    """Approval request response."""
    id: UUID
    run_id: UUID
    step_sequence: int
    approval_type: ApprovalType
    state: ApprovalState
    tool_name: str
    action: str
    resource: str | None
    input_data: dict[str, Any]
    policy_reason: str
    requested_by: str
    requested_at: datetime
    approved_by: str | None
    approved_at: datetime | None
    denial_reason: str | None
    expires_at: datetime | None
    response_data: dict[str, Any] | None

    @classmethod
    def from_entity(cls, request: ApprovalRequest) -> "ApprovalResponse":
        return cls(
            id=request.id,
            run_id=request.run_id,
            step_sequence=request.step_sequence,
            approval_type=request.approval_type,
            state=request.state,
            tool_name=request.tool_name,
            action=request.action,
            resource=request.resource,
            input_data=request.input_data,
            policy_reason=request.policy_reason,
            requested_by=request.requested_by,
            requested_at=request.requested_at,
            approved_by=request.approved_by,
            approved_at=request.approved_at,
            denial_reason=request.denial_reason,
            expires_at=request.expires_at,
            response_data=request.response_data,
        )


@dataclass(frozen=True, slots=True)
class ApprovalListResponse:
    approvals: list[ApprovalResponse]
    total: int