"""Approval API endpoints."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.api.v1.schemas.approvals import (
    ApprovalDecisionRequest,
    ApprovalListResponse,
    ApprovalResponse,
)
from app.infrastructure.auth.middleware import (
    AuthContext,
    get_current_tenant,
    require_scopes,
)
from app.domain.services.approval_coordinator import ApprovalCoordinator

router = APIRouter(prefix="/approvals", tags=["approvals"])


async def get_approval_coordinator() -> ApprovalCoordinator:
    """Dependency to get approval coordinator."""
    # This would be injected from the application container
    from app.main import app
    return app.state.approval_coordinator


@router.get("", response_model=ApprovalListResponse)
async def list_approvals(
    tenant_id: UUID = Depends(get_current_tenant),
    run_id: UUID | None = Query(None),
    state: str | None = Query(None),
    limit: int = Query(50, le=100),
    offset: int = Query(0, ge=0),
    approval_coordinator: ApprovalCoordinator = Depends(get_approval_coordinator),
    auth: AuthContext = Depends(require_scopes("approvals:read")),
) -> ApprovalListResponse:
    """List approval requests for tenant."""
    approvals = await approval_coordinator.get_pending_approvals(
        tenant_id=tenant_id,
        run_id=run_id,
    )
    
    # Filter by state if provided
    if state:
        approvals = [a for a in approvals if a.state.value == state]
    
    total = len(approvals)
    paginated = approvals[offset:offset + limit]
    
    return ApprovalListResponse(
        approvals=[ApprovalResponse.from_entity(a) for a in paginated],
        total=total,
    )


@router.get("/{approval_id}", response_model=ApprovalResponse)
async def get_approval(
    approval_id: UUID,
    tenant_id: UUID = Depends(get_current_tenant),
    approval_coordinator: ApprovalCoordinator = Depends(get_approval_coordinator),
    auth: AuthContext = Depends(require_scopes("approvals:read")),
) -> ApprovalResponse:
    """Get approval request details."""
    request = await approval_coordinator.get(approval_id)
    if not request:
        from app.infrastructure.error.errors import NotFoundError
        raise NotFoundError("Approval request not found")
    
    # Verify tenant access (run should belong to tenant)
    # This is enforced by RLS in the database
    return ApprovalResponse.from_entity(request)


@router.post("/{approval_id}/approve", response_model=ApprovalResponse)
async def approve_request(
    approval_id: UUID,
    decision: ApprovalDecisionRequest,
    tenant_id: UUID = Depends(get_current_tenant),
    approval_coordinator: ApprovalCoordinator = Depends(get_approval_coordinator),
    auth: AuthContext = Depends(require_scopes("approvals:write")),
) -> ApprovalResponse:
    """Approve a pending request."""
    request = await approval_coordinator.respond_to_approval(
        request_id=approval_id,
        approved=True,
        responded_by=auth.user_id or "unknown",
        response_data=decision.response_data,
    )
    return ApprovalResponse.from_entity(request)


@router.post("/{approval_id}/deny", response_model=ApprovalResponse)
async def deny_request(
    approval_id: UUID,
    decision: ApprovalDecisionRequest,
    tenant_id: UUID = Depends(get_current_tenant),
    approval_coordinator: ApprovalCoordinator = Depends(get_approval_coordinator),
    auth: AuthContext = Depends(require_scopes("approvals:write")),
) -> ApprovalResponse:
    """Deny a pending request."""
    if not decision.denial_reason:
        from app.infrastructure.error.errors import ValidationError
        raise ValidationError("Denial reason required")
    
    request = await approval_coordinator.respond_to_approval(
        request_id=approval_id,
        approved=False,
        responded_by=auth.user_id or "unknown",
        denial_reason=decision.denial_reason,
    )
    return ApprovalResponse.from_entity(request)


@router.post("/{approval_id}/cancel", response_model=ApprovalResponse)
async def cancel_request(
    approval_id: UUID,
    tenant_id: UUID = Depends(get_current_tenant),
    approval_coordinator: ApprovalCoordinator = Depends(get_approval_coordinator),
    auth: AuthContext = Depends(require_scopes("approvals:write")),
) -> ApprovalResponse:
    """Cancel a pending request."""
    request = await approval_coordinator.get(approval_id)
    if not request:
        from app.infrastructure.error.errors import NotFoundError
        raise NotFoundError("Approval request not found")
    
    request.cancel("Cancelled by user")
    await approval_coordinator.update(request)
    return ApprovalResponse.from_entity(request)