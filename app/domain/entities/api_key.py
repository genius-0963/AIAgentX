"""API Key entity."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from app.domain.entities.base import AggregateRoot


@dataclass(slots=True, kw_only=True)
class APIKey(AggregateRoot):
    """API Key entity."""

    tenant_id: UUID
    key_hash: str
    name: str | None = None
    scopes: dict[str, Any] = field(default_factory=dict)
    expires_at: datetime | None = None
    revoked_at: datetime | None = None
    last_used_at: datetime | None = None

    def __post_init__(self) -> None:
        if not self.key_hash:
            raise ValueError("Key hash cannot be empty")
        if not isinstance(self.scopes, dict):
            raise ValueError("Scopes must be a dictionary")

    def is_revoked(self) -> bool:
        """Check if key is revoked."""
        return self.revoked_at is not None

    def is_expired(self) -> bool:
        """Check if key is expired."""
        if self.expires_at is None:
            return False
        return datetime.now(UTC) > self.expires_at

    def is_valid(self) -> bool:
        """Check if key is valid (not revoked, not expired)."""
        return not self.is_revoked() and not self.is_expired()

    def has_scope(self, scope: str) -> bool:
        """Check if key has a specific scope."""
        return scope in self.scopes

    def revoke(self) -> None:
        """Revoke the API key."""
        if self.is_revoked():
            return
        self.revoked_at = datetime.now(UTC)
        self.touch()

    def record_usage(self) -> None:
        """Record key usage."""
        self.last_used_at = datetime.now(UTC)
        self.touch()
