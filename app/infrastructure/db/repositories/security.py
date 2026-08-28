"""SQL repository implementations for security domain."""

from __future__ import annotations

from datetime import datetime, UTC
from typing import Any
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.approval_request import (
    ApprovalRequest,
    ApprovalState,
    ApprovalType,
)
from app.domain.repositories.security import ApprovalRequestRepository
from app.infrastructure.db.models.approval import (
    ApprovalRequestModel,
    AuditLogModel,
)


class SQLApprovalRepository(ApprovalRequestRepository):
    """SQL implementation of approval request repository."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, request: ApprovalRequest) -> None:
        model = ApprovalRequestModel.from_entity(request)
        self._session.add(model)
        await self._session.flush()

    async def get(self, request_id: UUID) -> ApprovalRequest | None:
        result = await self._session.execute(
            select(ApprovalRequestModel).where(ApprovalRequestModel.id == request_id)
        )
        model = result.scalar_one_or_none()
        return model.to_entity() if model else None

    async def update(self, request: ApprovalRequest) -> None:
        result = await self._session.execute(
            select(ApprovalRequestModel).where(ApprovalRequestModel.id == request.id)
        )
        model = result.scalar_one()
        model.update_from_entity(request)
        await self._session.flush()

    async def get_pending(
        self,
        tenant_id: UUID,
        run_id: UUID | None = None,
    ) -> list[ApprovalRequest]:
        query = (
            select(ApprovalRequestModel)
            .join(ApprovalRequestModel.run)
            .where(ApprovalRequestModel.run.has(tenant_id=tenant_id))
            .where(ApprovalRequestModel.state == ApprovalState.PENDING)
        )
        if run_id:
            query = query.where(ApprovalRequestModel.run_id == run_id)

        result = await self._session.execute(query)
        return [m.to_entity() for m in result.scalars().all()]

    async def expire_old(self) -> int:
        result = await self._session.execute(
            update(ApprovalRequestModel)
            .where(ApprovalRequestModel.state == ApprovalState.PENDING)
            .where(ApprovalRequestModel.expires_at < datetime.now(UTC))
            .values(state=ApprovalState.EXPIRED)
        )
        return result.rowcount


class SQLAuditRepository:
    """SQL implementation of audit log repository."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, entry: Any) -> None:
        from app.application.services.audit_logger import AuditEntry

        model = AuditLogModel.from_entity(entry)
        self._session.add(model)
        await self._session.flush()

    async def query(
        self,
        tenant_id: UUID,
        run_id: UUID | None = None,
        event_types: list[Any] | None = None,
        tool_name: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Any]:
        from app.application.services.audit_logger import AuditEntry, AuditEventType

        query = select(AuditLogModel).where(AuditLogModel.tenant_id == tenant_id)

        if run_id:
            query = query.where(AuditLogModel.run_id == run_id)
        if event_types:
            query = query.where(AuditLogModel.event_type.in_([e.value for e in event_types]))
        if tool_name:
            query = query.where(AuditLogModel.tool_name == tool_name)
        if start_time:
            query = query.where(AuditLogModel.timestamp >= start_time)
        if end_time:
            query = query.where(AuditLogModel.timestamp <= end_time)

        query = query.order_by(AuditLogModel.timestamp.desc()).limit(limit).offset(offset)

        result = await self._session.execute(query)
        return [m.to_entity() for m in result.scalars().all()]

    async def count(
        self,
        tenant_id: UUID,
        run_id: UUID | None = None,
        event_types: list[Any] | None = None,
        tool_name: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> int:
        from app.application.services.audit_logger import AuditEventType

        query = select(sa.func.count()).select_from(AuditLogModel).where(AuditLogModel.tenant_id == tenant_id)

        if run_id:
            query = query.where(AuditLogModel.run_id == run_id)
        if event_types:
            query = query.where(AuditLogModel.event_type.in_([e.value for e in event_types]))
        if tool_name:
            query = query.where(AuditLogModel.tool_name == tool_name)
        if start_time:
            query = query.where(AuditLogModel.timestamp >= start_time)
        if end_time:
            query = query.where(AuditLogModel.timestamp <= end_time)

        result = await self._session.execute(query)
        return result.scalar_one()

    async def get_stats(
        self,
        tenant_id: UUID,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> dict[str, Any]:
        from app.application.services.audit_logger import AuditEventType

        query = select(
            AuditLogModel.event_type,
            sa.func.count().label("count"),
        ).where(AuditLogModel.tenant_id == tenant_id).group_by(AuditLogModel.event_type)

        if start_time:
            query = query.where(AuditLogModel.timestamp >= start_time)
        if end_time:
            query = query.where(AuditLogModel.timestamp <= end_time)

        result = await self._session.execute(query)
        by_event_type = {row.event_type: row.count for row in result}

        # Get tool breakdown
        tool_query = select(
            AuditLogModel.tool_name,
            sa.func.count().label("count"),
        ).where(AuditLogModel.tenant_id == tenant_id).group_by(AuditLogModel.tool_name)

        if start_time:
            tool_query = tool_query.where(AuditLogModel.timestamp >= start_time)
        if end_time:
            tool_query = tool_query.where(AuditLogModel.timestamp <= end_time)

        tool_result = await self._session.execute(tool_query)
        by_tool = {row.tool_name: row.count for row in tool_result if row.tool_name}

        # Calculate rates
        total = sum(by_event_type.values())
        approval_requested = by_event_type.get("approval_requested", 0)
        approval_granted = by_event_type.get("approval_granted", 0)
        approval_denied = by_event_type.get("approval_denied", 0)
        rate_limited = by_event_type.get("rate_limited", 0)

        approval_rate = (approval_granted / approval_requested * 100) if approval_requested > 0 else 0
        denial_rate = (approval_denied / approval_requested * 100) if approval_requested > 0 else 0

        return {
            "total_events": total,
            "by_event_type": by_event_type,
            "by_tool": by_tool,
            "approval_rate": approval_rate,
            "denial_rate": denial_rate,
            "rate_limit_hits": rate_limited,
        }