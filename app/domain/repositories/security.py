"""Repository interfaces for tool security domain."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from app.domain.entities.approval_request import ApprovalRequest
from app.domain.entities.approval_request import ApprovalState
from app.domain.entities.approval_request import ApprovalType
from app.domain.entities.tool_grant import ToolGrant


class ToolGrantRepository:
    """Repository interface for tool grants."""

    async def get_by_tool(self, agent_version_id: UUID, tool_name: str) -> ToolGrant | None:
        raise NotImplementedError

    async def add(self, grant: ToolGrant) -> None:
        raise NotImplementedError

    async def update(self, grant: ToolGrant) -> None:
        raise NotImplementedError

    async def get_by_agent_version(self, agent_version_id: UUID) -> list[ToolGrant]:
        raise NotImplementedError


class ApprovalRequestRepository:
    """Repository interface for approval requests."""

    async def add(self, request: ApprovalRequest) -> None:
        raise NotImplementedError

    async def get(self, request_id: UUID) -> ApprovalRequest | None:
        raise NotImplementedError

    async def update(self, request: ApprovalRequest) -> None:
        raise NotImplementedError

    async def get_pending(
        self,
        tenant_id: UUID,
        run_id: UUID | None = None,
    ) -> list[ApprovalRequest]:
        raise NotImplementedError

    async def expire_old(self) -> int:
        raise NotImplementedError