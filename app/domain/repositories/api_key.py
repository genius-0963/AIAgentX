"""API Key repository protocol."""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from app.domain.entities.api_key import APIKey


class APIKeyRepository(Protocol):
    """Repository for API key operations."""

    async def create(self, api_key: APIKey) -> APIKey:
        """Create a new API key."""
        ...

    async def get(self, key_id: UUID) -> APIKey | None:
        """Get API key by ID."""
        ...

    async def get_by_hash(self, key_hash: str) -> APIKey | None:
        """Get API key by hash."""
        ...

    async def update(self, api_key: APIKey) -> APIKey:
        """Update API key."""
        ...

    async def list(
        self,
        tenant_id: UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> list[APIKey]:
        """List API keys for tenant."""
        ...

    async def revoke(self, key_id: UUID) -> bool:
        """Revoke API key."""
        ...

    async def cleanup_expired(self) -> int:
        """Clean up expired API keys. Returns count."""
        ...
