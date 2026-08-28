"""Audit API endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.api.v1.schemas.audit import (
    AuditLogEntry,
    AuditLogListResponse,
    AuditStatsResponse,
)
from app.application.auth.dependencies import (
    AuthContext,
    get_current_tenant,
    require_scopes,
)
from app.application.services.audit_logger import AuditEventType, AuditLogger

router = APIRouter(prefix="/audit", tags=["audit"])


async def get_audit_logger() -> AuditLogger:
    """Dependency to get audit logger."""
    from app.main import app
    return app.state.audit_logger


@router.get("", response_model=AuditLogListResponse)
async def list_audit_logs(
    tenant_id: UUID = Depends(get_current_tenant),
    run_id: UUID | None = Query(None),
    event_type: str | None = Query(None),
    tool_name: str | None = Query(None),
    start_time: datetime | None = Query(None),
    end_time: datetime | None = Query(None),
    limit: int = Query(100, le=1000),
    offset: int = Query(0, ge=0),
    audit_logger: AuditLogger = Depends(get_audit_logger),
    auth: AuthContext = Depends(require_scopes("audit:read")),
) -> AuditLogListResponse:
    """Query audit logs."""
    event_types = [AuditEventType(event_type)] if event_type else None
    
    entries = await audit_logger.query(
        tenant_id=tenant_id,
        run_id=run_id,
        event_types=event_types,
        tool_name=tool_name,
        start_time=start_time,
        end_time=end_time,
        limit=limit,
        offset=offset,
    )
    total = await audit_logger._repo.count(
        tenant_id=tenant_id,
        run_id=run_id,
        event_types=event_types,
        tool_name=tool_name,
        start_time=start_time,
        end_time=end_time,
    )
    
    return AuditLogListResponse(
        entries=[AuditLogEntry.from_entity(e) for e in entries],
        total=total,
    )


@router.get("/stats", response_model=AuditStatsResponse)
async def get_audit_stats(
    tenant_id: UUID = Depends(get_current_tenant),
    start_time: datetime | None = Query(None),
    end_time: datetime | None = Query(None),
    audit_logger: AuditLogger = Depends(get_audit_logger),
    auth: AuthContext = Depends(require_scopes("audit:read")),
) -> AuditStatsResponse:
    """Get audit statistics."""
    stats = await audit_logger.get_stats(tenant_id, start_time, end_time)
    return AuditStatsResponse(**stats)