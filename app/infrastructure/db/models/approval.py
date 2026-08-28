"""Approval and Audit SQLAlchemy models."""

from __future__ import annotations

from datetime import datetime, UTC
from typing import Any
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy import Enum, ForeignKey, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.entities.approval_request import (
    ApprovalRequest,
    ApprovalState,
    ApprovalType,
)
from app.infrastructure.db.base import Base, TimestampMixin, UUIDMixin


class ApprovalRequestModel(Base, UUIDMixin, TimestampMixin):
    """Approval Request database model."""

    __tablename__ = "approval_requests"

    run_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    step_sequence: Mapped[int] = mapped_column(sa.Integer(), nullable=False)
    approval_type: Mapped[ApprovalType] = mapped_column(
        Enum(ApprovalType, name="approval_type", create_constraint=False),
        nullable=False,
    )
    state: Mapped[ApprovalState] = mapped_column(
        Enum(ApprovalState, name="approval_state", create_constraint=False),
        nullable=False,
        default=ApprovalState.PENDING,
    )
    tool_name: Mapped[str] = mapped_column(Text(), nullable=False)
    action: Mapped[str] = mapped_column(Text(), nullable=False)
    resource: Mapped[str | None] = mapped_column(Text(), nullable=True)
    input_data: Mapped[dict[str, Any]] = mapped_column(JSONB(), nullable=False, default={})
    policy_reason: Mapped[str] = mapped_column(Text(), nullable=False, default="")
    requested_by: Mapped[str] = mapped_column(Text(), nullable=False, default="system")
    requested_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )
    approved_by: Mapped[str | None] = mapped_column(Text(), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)
    denial_reason: Mapped[str | None] = mapped_column(Text(), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)
    ttl_seconds: Mapped[int] = mapped_column(sa.Integer(), nullable=False, default=3600)
    response_data: Mapped[dict[str, Any] | None] = mapped_column(JSONB(), nullable=True)

    run: Mapped["RunModel"] = relationship("RunModel", back_populates="approval_requests")

    def to_entity(self) -> ApprovalRequest:
        """Convert to domain entity."""
        return ApprovalRequest(
            id=self.id,
            created_at=self.created_at,
            updated_at=self.updated_at,
            run_id=self.run_id,
            step_sequence=self.step_sequence,
            approval_type=self.approval_type,
            state=self.state,
            tool_name=self.tool_name,
            action=self.action,
            resource=self.resource,
            input_data=self.input_data or {},
            policy_reason=self.policy_reason,
            requested_by=self.requested_by,
            requested_at=self.requested_at,
            approved_by=self.approved_by,
            approved_at=self.approved_at,
            denial_reason=self.denial_reason,
            expires_at=self.expires_at,
            ttl_seconds=self.ttl_seconds,
            response_data=self.response_data,
        )

    @classmethod
    def from_entity(cls, request: ApprovalRequest) -> "ApprovalRequestModel":
        """Create model from domain entity."""
        return cls(
            id=request.id,
            created_at=request.created_at,
            updated_at=request.updated_at,
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
            ttl_seconds=request.ttl_seconds,
            response_data=request.response_data,
        )

    def update_from_entity(self, request: ApprovalRequest) -> None:
        """Update model from domain entity."""
        self.state = request.state
        self.approved_by = request.approved_by
        self.approved_at = request.approved_at
        self.denial_reason = request.denial_reason
        self.response_data = request.response_data
        self.updated_at = datetime.now(UTC)


class AuditLogModel(Base, UUIDMixin, TimestampMixin):
    """Audit Log database model."""

    __tablename__ = "audit_logs"

    timestamp: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )
    tenant_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    run_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("runs.id", ondelete="SET NULL"),
        nullable=True,
    )
    agent_version_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("agent_versions.id", ondelete="SET NULL"),
        nullable=True,
    )
    event_type: Mapped[str] = mapped_column(Text(), nullable=False)
    tool_name: Mapped[str | None] = mapped_column(Text(), nullable=True)
    action: Mapped[str | None] = mapped_column(Text(), nullable=True)
    resource: Mapped[str | None] = mapped_column(Text(), nullable=True)
    input_data: Mapped[dict[str, Any] | None] = mapped_column(JSONB(), nullable=True)
    output_data: Mapped[dict[str, Any] | None] = mapped_column(JSONB(), nullable=True)
    success: Mapped[bool] = mapped_column(sa.Boolean(), nullable=False)
    reason: Mapped[str] = mapped_column(Text(), nullable=False)
    meta: Mapped[dict[str, Any]] = mapped_column(JSONB(), nullable=False, default={})
    approval_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("approval_requests.id", ondelete="SET NULL"),
        nullable=True,
    )
    user_id: Mapped[str | None] = mapped_column(Text(), nullable=True)

    def to_entity(self) -> Any:
        """Convert to domain entity."""
        from app.application.services.audit_logger import AuditEntry, AuditEventType

        return AuditEntry(
            id=self.id,
            timestamp=self.timestamp,
            tenant_id=self.tenant_id,
            run_id=self.run_id,
            agent_version_id=self.agent_version_id,
            event_type=AuditEventType(self.event_type),
            tool_name=self.tool_name,
            action=self.action,
            resource=self.resource,
            input_data=self.input_data,
            output_data=self.output_data,
            success=self.success,
            reason=self.reason,
            metadata=self.meta or {},
            approval_id=self.approval_id,
            user_id=self.user_id,
        )

    @classmethod
    def from_entity(cls, entry: Any) -> "AuditLogModel":
        """Create model from domain entity."""
        from app.application.services.audit_logger import AuditEntry

        entry = entry  # type: AuditEntry
        return cls(
            id=entry.id,
            created_at=entry.timestamp,
            updated_at=entry.timestamp,
            timestamp=entry.timestamp,
            tenant_id=entry.tenant_id,
            run_id=entry.run_id,
            agent_version_id=entry.agent_version_id,
            event_type=entry.event_type.value,
            tool_name=entry.tool_name,
            action=entry.action,
            resource=entry.resource,
            input_data=entry.input_data,
            output_data=entry.output_data,
            success=entry.success,
            reason=entry.reason,
            meta=entry.metadata,
            approval_id=entry.approval_id,
            user_id=entry.user_id,
        )