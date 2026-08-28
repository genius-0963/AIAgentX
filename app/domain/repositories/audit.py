"""Audit repository interface."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

if TYPE_CHECKING:
    from app.domain.entities.audit import AuditEventType, AuditLogEntry


class AuditRepository:
    """Repository interface for audit logs."""

    async def add(self, entry: AuditLogEntry) -> None:
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
    ) -> list[AuditLogEntry]:
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