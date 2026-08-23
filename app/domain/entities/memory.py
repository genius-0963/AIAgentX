"""Memory-related domain entities."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any
from uuid import UUID

from app.domain.entities.base import Entity, AggregateRoot


class MemoryScope(str, Enum):
    """Memory storage scope."""

    EPHEMERAL = "ephemeral"
    SESSION = "session"
    DURABLE = "durable"


class AllowedUseLabel(str, Enum):
    """Data classification labels for memory content."""

    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"


@dataclass(slots=True, kw_only=True)
class MemoryRecord(Entity):
    """A single memory record with embedding."""

    tenant_id: UUID
    agent_id: UUID
    scope: MemoryScope
    namespace: str
    content_ciphertext: str
    embedding: list[float] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    allowed_use_label: AllowedUseLabel = AllowedUseLabel.PUBLIC
    session_id: str | None = None
    expires_at: datetime | None = None

    def is_expired(self) -> bool:
        """Check if the memory record has expired."""
        if self.expires_at is None:
            return False
        return datetime.now(UTC) >= self.expires_at

    def is_encrypted(self) -> bool:
        """Check if content is encrypted."""
        return bool(self.content_ciphertext)


@dataclass(slots=True, kw_only=True)
class SessionSummary(Entity):
    """Summary of a session's memory for efficiency."""

    tenant_id: UUID
    agent_id: UUID
    session_id: str
    summary_ciphertext: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def touch(self) -> None:
        """Update the updated_at timestamp."""
        self.updated_at = datetime.now(UTC)


@dataclass(slots=True, kw_only=True)
class MemoryRetentionPolicy(Entity):
    """Retention policy for memory records."""

    tenant_id: UUID
    scope: MemoryScope
    retention_days: int
    max_records_per_tenant: int | None = None
    max_storage_mb: int | None = None

    def __post_init__(self) -> None:
        """Validate retention policy."""
        if self.retention_days <= 0:
            raise ValueError("retention_days must be positive")
        if self.max_records_per_tenant is not None and self.max_records_per_tenant <= 0:
            raise ValueError("max_records_per_tenant must be positive")
        if self.max_storage_mb is not None and self.max_storage_mb <= 0:
            raise ValueError("max_storage_mb must be positive")

    def calculate_expiry(self) -> datetime:
        """Calculate expiry date based on retention days."""
        from datetime import timedelta

        return datetime.now(UTC) + timedelta(days=self.retention_days)

    def is_quota_exceeded(
        self,
        current_record_count: int,
        current_storage_mb: int,
    ) -> tuple[bool, str]:
        """Check if quota limits are exceeded.

        Returns:
            Tuple of (is_exceeded, reason)
        """
        if self.max_records_per_tenant is not None and current_record_count >= self.max_records_per_tenant:
            return True, f"Record count {current_record_count} exceeds limit {self.max_records_per_tenant}"

        if self.max_storage_mb is not None and current_storage_mb >= self.max_storage_mb:
            return True, f"Storage {current_storage_mb}MB exceeds limit {self.max_storage_mb}MB"

        return False, ""


@dataclass(slots=True, kw_only=True)
class MemoryAggregate(AggregateRoot):
    """Aggregate root for memory operations."""

    record: MemoryRecord

    def add_content(self, content: str, is_encrypted: bool = False) -> None:
        """Add content to the memory record."""
        if is_encrypted:
            self.record.content_ciphertext = content
        else:
            self.record.content_ciphertext = content  # Will be encrypted in service layer
        self.touch()

    def update_embedding(self, embedding: list[float]) -> None:
        """Update the embedding vector."""
        self.record.embedding = embedding
        self.touch()

    def set_expiry(self, expires_at: datetime | None) -> None:
        """Set expiry time for the record."""
        self.record.expires_at = expires_at
        self.touch()

    def mark_as_expired(self) -> None:
        """Mark the record as expired."""
        self.record.expires_at = datetime.now(UTC)
        self.touch()
