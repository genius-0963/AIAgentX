"""Memory SQLAlchemy models."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Text, Index
from sqlalchemy.dialects.postgresql import ARRAY, UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.entities.memory import (
    AllowedUseLabel,
    MemoryRecord,
    MemoryRetentionPolicy,
    MemoryScope,
    SessionSummary,
)
from app.infrastructure.db.base import Base, TimestampMixin, UUIDMixin


class MemoryRecordModel(Base, UUIDMixin, TimestampMixin):
    """Memory record database model."""

    __tablename__ = "memory_records"

    tenant_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    agent_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    scope: Mapped[str] = mapped_column(Text(), nullable=False)
    namespace: Mapped[str] = mapped_column(Text(), nullable=False, index=True)
    content_ciphertext: Mapped[str] = mapped_column(Text(), nullable=False)
    embedding: Mapped[list[float] | None] = mapped_column(ARRAY(float), nullable=True)
    metadata: Mapped[dict] = mapped_column(JSONB(astext_type=Text()), nullable=False, default=dict)
    allowed_use_label: Mapped[str] = mapped_column(Text(), nullable=False)
    session_id: Mapped[str | None] = mapped_column(Text(), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)

    __table_args__ = (
        Index("ix_memory_records_tenant_agent", "tenant_id", "agent_id"),
        Index("ix_memory_records_expires_at", "expires_at"),
    )

    def to_entity(self) -> MemoryRecord:
        """Convert to domain entity."""
        return MemoryRecord(
            id=self.id,
            tenant_id=self.tenant_id,
            agent_id=self.agent_id,
            scope=MemoryScope(self.scope),
            namespace=self.namespace,
            content_ciphertext=self.content_ciphertext,
            embedding=self.embedding,
            metadata=self.metadata,
            allowed_use_label=AllowedUseLabel(self.allowed_use_label),
            session_id=self.session_id,
            expires_at=self.expires_at,
            created_at=self.created_at,
            updated_at=self.updated_at,
        )

    @classmethod
    def from_entity(cls, record: MemoryRecord) -> MemoryRecordModel:
        """Create from domain entity."""
        return cls(
            id=record.id,
            tenant_id=record.tenant_id,
            agent_id=record.agent_id,
            scope=record.scope.value,
            namespace=record.namespace,
            content_ciphertext=record.content_ciphertext,
            embedding=record.embedding,
            metadata=record.metadata,
            allowed_use_label=record.allowed_use_label.value,
            session_id=record.session_id,
            expires_at=record.expires_at,
            created_at=record.created_at,
            updated_at=record.updated_at,
        )


class SessionSummaryModel(Base, UUIDMixin, TimestampMixin):
    """Session summary database model."""

    __tablename__ = "session_summaries"

    tenant_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    agent_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    session_id: Mapped[str] = mapped_column(Text(), nullable=False, index=True)
    summary_ciphertext: Mapped[str] = mapped_column(Text(), nullable=False)
    metadata: Mapped[dict] = mapped_column(JSONB(astext_type=Text()), nullable=False, default=dict)

    __table_args__ = (
        Index("ix_session_summaries_tenant_agent", "tenant_id", "agent_id"),
        Index("ix_session_summaries_session_id", "session_id"),
    )

    def to_entity(self) -> SessionSummary:
        """Convert to domain entity."""
        return SessionSummary(
            id=self.id,
            tenant_id=self.tenant_id,
            agent_id=self.agent_id,
            session_id=self.session_id,
            summary_ciphertext=self.summary_ciphertext,
            metadata=self.metadata,
            created_at=self.created_at,
            updated_at=self.updated_at,
        )

    @classmethod
    def from_entity(cls, summary: SessionSummary) -> SessionSummaryModel:
        """Create from domain entity."""
        return cls(
            id=summary.id,
            tenant_id=summary.tenant_id,
            agent_id=summary.agent_id,
            session_id=summary.session_id,
            summary_ciphertext=summary.summary_ciphertext,
            metadata=summary.metadata,
            created_at=summary.created_at,
            updated_at=summary.updated_at,
        )


class MemoryRetentionPolicyModel(Base, UUIDMixin, TimestampMixin):
    """Memory retention policy database model."""

    __tablename__ = "memory_retention_policies"

    tenant_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    scope: Mapped[str] = mapped_column(Text(), nullable=False)
    retention_days: Mapped[int] = mapped_column(nullable=False)
    max_records_per_tenant: Mapped[int | None] = mapped_column(nullable=True)
    max_storage_mb: Mapped[int | None] = mapped_column(nullable=True)

    __table_args__ = (
        Index("ix_retention_policies_tenant_id", "tenant_id"),
    )

    def to_entity(self) -> MemoryRetentionPolicy:
        """Convert to domain entity."""
        return MemoryRetentionPolicy(
            id=self.id,
            tenant_id=self.tenant_id,
            scope=MemoryScope(self.scope),
            retention_days=self.retention_days,
            max_records_per_tenant=self.max_records_per_tenant,
            max_storage_mb=self.max_storage_mb,
            created_at=self.created_at,
            updated_at=self.updated_at,
        )

    @classmethod
    def from_entity(cls, policy: MemoryRetentionPolicy) -> MemoryRetentionPolicyModel:
        """Create from domain entity."""
        return cls(
            id=policy.id,
            tenant_id=policy.tenant_id,
            scope=policy.scope.value,
            retention_days=policy.retention_days,
            max_records_per_tenant=policy.max_records_per_tenant,
            max_storage_mb=policy.max_storage_mb,
            created_at=policy.created_at,
            updated_at=policy.updated_at,
        )
