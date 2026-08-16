"""User repository protocol."""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from app.domain.entities.user import User


class UserRepository(Protocol):
    """Repository for user operations."""

    async def create(self, user: User) -> User:
        """Create a new user."""
        ...

    async def get(self, user_id: UUID) -> User | None:
        """Get user by ID."""
        ...

    async def get_by_email(self, tenant_id: UUID, email: str) -> User | None:
        """Get user by email within tenant."""
        ...

    async def update(self, user: User) -> User:
        """Update user."""
        ...

    async def list(
        self,
        tenant_id: UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> list[User]:
        """List users for tenant."""
        ...

    async def delete(self, user_id: UUID) -> bool:
        """Delete user."""
        ...
