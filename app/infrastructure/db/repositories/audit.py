"""Audit SQLAlchemy repository implementation with outbox pattern."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.audit import AuditEventType, AuditLogEntry
from app.domain.repositories.audit import AuditRepository
from app.infrastructure.db.models.audit import AuditLogModel
from app.infrastructure.db.models.outbox import OutboxEventModel
from app.infrastructure.db.repositories.base import BaseRepository

if TYPE_CHECKING:
    from app.domain.entities.audit import AuditLogEntry


class SQLAuditRepository(BaseRepository[AuditLogEntry, AuditLogModel], AuditRepository):
    """SQLAlchemy implementation of AuditRepository with outbox pattern."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, AuditLogModel, AuditLogEntry)
        self._outbox_model = OutboxEventModel

    def _to_entity(self, model: AuditLogModel) -> AuditLogEntry:
        return model.to_entity()

    def _to_model(self, entity: AuditLogEntry) -> AuditLogModel:
        return AuditLogModel.from_entity(entity)

    async def add(self, entry: AuditLogEntry) -> None:
        """Add audit entry with outbox event for reliable delivery."""
        # Add audit log entry
        model = self._to_model(entry)
        await self._add(model)

        # Add outbox event for reliable delivery
        outbox_event = OutboxEventModel(
            event_type="audit_log",
            aggregate_id=str(entry.tenant_id),
            aggregate_type="tenant",
            payload={
                "audit_entry_id": str(entry.id),
                "event_type": entry.event_type.value,
                "tenant_id": entry.tenant_id,
            },
        )
        self._session.add(outbox_event)

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
    ) -> list[AuditLogEntry]:
        stmt = select(AuditLogModel).where(AuditLogModel.tenant_id == str(tenant_id))

        if run_id:
            stmt = stmt.where(AuditLogModel.run_id == str(run_id))

        if event_types:
            stmt = stmt.where(AuditLogModel.event_type.in_([et.value for et in event_types]))

        if tool_name:
            stmt = stmt.where(AuditLogModel.tool_name == tool_name)

        if start_time:
            stmt = stmt.where(AuditLogModel.created_at >= start_time)

        if end_time:
            stmt = stmt.where(AuditLogModel.created_at <= end_time)

        stmt = stmt.order_by(AuditLogModel.created_at.desc()).limit(limit).offset(offset)

        result = await self._session.execute(stmt)
        return [self._to_entity(m) for m in result.scalars().all()]

    async def count(
        self,
        tenant_id: UUID,
        run_id: UUID | None = None,
        event_types: list[AuditEventType] | None = None,
        tool_name: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> int:
        stmt = select(func.count(AuditLogModel.id)).where(AuditLogModel.tenant_id == str(tenant_id))

        if run_id:
            stmt = stmt.where(AuditLogModel.run_id == str(run_id))

        if event_types:
            stmt = stmt.where(AuditLogModel.event_type.in_([et.value for et in event_types]))

        if tool_name:
            stmt = stmt.where(AuditLogModel.tool_name == tool_name)

        if start_time:
            stmt = stmt.where(AuditLogModel.created_at >= start_time)

        if end_time:
            stmt = stmt.where(AuditLogModel.created_at <= end_time)

        result = await self._session.execute(stmt)
        return result.scalar() or 0

    async def get_stats(
        self,
        tenant_id: UUID,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> dict[str, Any]:
        # Base query for tenant
        base_stmt = select(AuditLogModel).where(AuditLogModel.tenant_id == str(tenant_id))

        if start_time:
            base_stmt = base_stmt.where(AuditLogModel.created_at >= start_time)
        if end_time:
            base_stmt = base_stmt.where(AuditLogModel.created_at <= end_time)

        # Total count
        total_stmt = select(func.count(AuditLogModel.id)).select_from(base_stmt.subquery())
        total_result = await self._session.execute(total_stmt)
        total = total_result.scalar() or 0

        # Count by event type
        type_stmt = (
            select(AuditLogModel.event_type, func.count(AuditLogModel.id))
            .where(AuditLogModel.tenant_id == str(tenant_id))
            .group_by(AuditLogModel.event_type)
        )
        if start_time:
            type_stmt = type_stmt.where(AuditLogModel.created_at >= start_time)
        if end_time:
            type_stmt = type_stmt.where(AuditLogModel.created_at <= end_time)

        type_result = await self._session.execute(type_stmt)
        by_type = {row[0]: row[1] for row in type_result.all()}

        # Count by tool
        tool_stmt = (
            select(AuditLogModel.tool_name, func.count(AuditLogModel.id))
            .where(AuditLogModel.tenant_id == str(tenant_id))
            .group_by(AuditLogModel.tool_name)
        )
        if start_time:
            tool_stmt = tool_stmt.where(AuditLogModel.created_at >= start_time)
        if end_time:
            tool_stmt = tool_stmt.where(AuditLogModel.created_at <= end_time)

        tool_result = await self._session.execute(tool_stmt)
        by_tool = {row[0]: row[1] for row in tool_result.all() if row[0]}

        # Success/failure counts
        success_stmt = (
            select(AuditLogModel.success, func.count(AuditLogModel.id))
            .where(AuditLogModel.tenant_id == str(tenant_id))
            .group_by(AuditLogModel.success)
        )
        if start_time:
            success_stmt = success_stmt.where(AuditLogModel.created_at >= start_time)
        if end_time:
            success_stmt = success_stmt.where(AuditLogModel.created_at <= end_time)

        success_result = await self._session.execute(success_stmt)
        by_success = {str(row[0]): row[1] for row in success_result.all()}

        return {
            "total": total,
            "by_event_type": by_type,
            "by_tool": by_tool,
            "by_success": by_success,
        }