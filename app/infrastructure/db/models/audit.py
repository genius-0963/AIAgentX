"""Audit log database model."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import ForeignKey, Index, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.domain.entities.audit import AuditLogEntry


class AuditLogModel(Base, UUIDMixin, TimestampMixin):
    """Audit log database model."""

    __tablename__ = "audit_logs"

    tenant_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("tenants.id"), nullable=False, index=True
    )
    run_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False), ForeignKey("runs.id"), nullable=True, index=True
    )
    agent_version_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False), ForeignKey("agent_versions.id"), nullable=True, index=True
    )
    event_type: Mapped[str] = mapped_column(Text(), nullable=False, index=True)
    tool_name: Mapped[str | None] = mapped_column(Text(), nullable=True, index=True)
    action: Mapped[str | None] = mapped_column(Text(), nullable=True)
    resource: Mapped[str | None] = mapped_column(Text(), nullable=True)
    input_data: Mapped[dict[str, Any]] = mapped_column(
        JSONB(astext_type=Text()), nullable=True, default=dict
    )
    output_data: Mapped[dict[str, Any]] = mapped_column(
        JSONB(astext_type=Text()), nullable=True, default=dict
    )
    success: Mapped[bool] = mapped_column(nullable=False, default=True)
    reason: Mapped[str] = mapped_column(Text(), nullable=True, default="")
    audit_metadata: Mapped[dict[str, Any]] = mapped_column(
        JSONB(astext_type=Text()), nullable=True, default=dict
    )
    approval_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False), nullable=True, index=True)
    user_id: Mapped[str | None] = mapped_column(Text(), nullable=True)

    __table_args__ = (
        Index("ix_audit_logs_tenant_created", "tenant_id", "created_at"),
        Index("ix_audit_logs_tenant_event_created", "tenant_id", "event_type", "created_at"),
    )

    def to_entity(self) -> AuditLogEntry:
        """Convert to domain entity."""
        from uuid import UUID

        from app.domain.entities.audit import AuditEventType, AuditLogEntry

        return AuditLogEntry(
            id=self.id,
            timestamp=self.created_at,
            tenant_id=UUID(self.tenant_id),
            run_id=UUID(self.run_id) if self.run_id else None,
            agent_version_id=UUID(self.agent_version_id) if self.agent_version_id else None,
            event_type=AuditEventType(self.event_type),
            tool_name=self.tool_name,
            action=self.action,
            resource=self.resource,
            input_data=self.input_data or {},
            output_data=self.output_data or {},
            success=self.success,
            reason=self.reason or "",
            metadata=self.audit_metadata or {},
            approval_id=UUID(self.approval_id) if self.approval_id else None,
            user_id=self.user_id,
        )

    @classmethod
    def from_entity(cls, entry: AuditLogEntry) -> AuditLogModel:
        """Create from domain entity."""
        return cls(
            id=str(entry.id),
            tenant_id=str(entry.tenant_id),
            run_id=str(entry.run_id) if entry.run_id else None,
            agent_version_id=str(entry.agent_version_id) if entry.agent_version_id else None,
            event_type=entry.event_type.value,
            tool_name=entry.tool_name,
            action=entry.action,
            resource=entry.resource,
            input_data=entry.input_data,
            output_data=entry.output_data,
            success=entry.success,
            reason=entry.reason,
            audit_metadata=entry.metadata,
            approval_id=str(entry.approval_id) if entry.approval_id else None,
            user_id=entry.user_id,
            created_at=entry.timestamp,
            updated_at=entry.timestamp,
        )