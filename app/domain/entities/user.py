"""User entity."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from app.domain.entities.base import AggregateRoot


@dataclass(slots=True, kw_only=True)
class User(AggregateRoot):
    """User entity."""

    tenant_id: UUID
    email: str
    password_hash: str
    status: str = "active"
    last_login_at: datetime | None = None

    def __post_init__(self) -> None:
        if not self.email or not self.email.strip():
            raise ValueError("Email cannot be empty")
        if "@" not in self.email:
            raise ValueError("Invalid email format")
        if not self.password_hash:
            raise ValueError("Password hash cannot be empty")

    def verify_password(self, password_hash: str) -> bool:
        """Verify password hash."""
        return self.password_hash == password_hash

    def update_password(self, new_password_hash: str) -> None:
        """Update password hash."""
        if not new_password_hash:
            raise ValueError("Password hash cannot be empty")
        self.password_hash = new_password_hash
        self.touch()

    def record_login(self) -> None:
        """Record login timestamp."""
        self.last_login_at = datetime.now(UTC)
        self.touch()

    def deactivate(self) -> None:
        """Deactivate user."""
        if self.status == "inactive":
            return
        self.status = "inactive"
        self.touch()

    def activate(self) -> None:
        """Activate user."""
        if self.status == "active":
            return
        self.status = "active"
        self.touch()

    def is_active(self) -> bool:
        """Check if user is active."""
        return self.status == "active"
