from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, UTC
from typing import Any
from uuid import UUID

from app.domain.entities.approval_request import ApprovalRequest, ApprovalState, ApprovalType


class ApprovalRequestRepository(ABC):
    """Repository interface for approval requests."""

    @abstractmethod
    async def add(self, request: ApprovalRequest) -> None:
        pass

    @abstractmethod
    async def get(self, request_id: UUID) -> ApprovalRequest | None:
        pass

    @abstractmethod
    async def update(self, request: ApprovalRequest) -> None:
        pass

    @abstractmethod
    async def get_pending(
        self,
        tenant_id: UUID,
        run_id: UUID | None = None,
    ) -> list[ApprovalRequest]:
        pass

    @abstractmethod
    async def expire_old(self) -> int:
        pass


class NotificationService(ABC):
    """Notification service interface."""

    @abstractmethod
    async def notify_approval_requested(self, request: ApprovalRequest) -> None:
        pass

    @abstractmethod
    async def notify_approval_responded(self, request: ApprovalRequest) -> None:
        pass


class ApprovalCoordinator:
    """Coordinates approval requests and responses."""

    def __init__(
        self,
        approval_repo: ApprovalRequestRepository,
        notification_service: NotificationService,
    ) -> None:
        self._repo = approval_repo
        self._notifications = notification_service

    async def request_approval(
        self,
        run_id: UUID,
        step_sequence: int,
        tool_name: str,
        action: str,
        resource: str | None,
        input_data: dict[str, Any],
        policy_reason: str,
        requested_by: str,
        ttl_seconds: int = 3600,
        approval_type: ApprovalType = ApprovalType.TOOL_EXECUTION,
    ) -> ApprovalRequest:
        """Create and store approval request."""
        request = ApprovalRequest(
            run_id=run_id,
            step_sequence=step_sequence,
            approval_type=approval_type,
            tool_name=tool_name,
            action=action,
            resource=resource,
            input_data=input_data,
            policy_reason=policy_reason,
            requested_by=requested_by,
            ttl_seconds=ttl_seconds,
        )

        await self._repo.add(request)
        await self._notifications.notify_approval_requested(request)
        return request

    async def respond_to_approval(
        self,
        request_id: UUID,
        approved: bool,
        responded_by: str,
        response_data: dict[str, Any] | None = None,
        denial_reason: str | None = None,
    ) -> ApprovalRequest:
        """Process approval response."""
        request = await self._repo.get(request_id)
        if not request:
            raise ValueError("Approval request not found")

        if approved:
            request.approve(responded_by, response_data)
        else:
            request.deny(responded_by, denial_reason or "Denied by approver")

        await self._repo.update(request)
        await self._notifications.notify_approval_responded(request)
        return request

    async def get_pending_approvals(
        self,
        tenant_id: UUID,
        run_id: UUID | None = None,
    ) -> list[ApprovalRequest]:
        """Get pending approvals for a tenant/run."""
        return await self._repo.get_pending(tenant_id, run_id)

    async def get(self, request_id: UUID) -> ApprovalRequest | None:
        """Get approval request by ID."""
        return await self._repo.get(request_id)

    async def update(self, request: ApprovalRequest) -> None:
        """Update approval request."""
        await self._repo.update(request)

    async def expire_old_requests(self) -> int:
        """Expire old pending requests. Returns count expired."""
        return await self._repo.expire_old()