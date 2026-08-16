"""Tenant repository protocol."""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from app.domain.entities.tenant import Tenant, TenantPlan, TenantStatus


class TenantRepository(Protocol):
    """Repository for tenant operations."""

    async def create(self, tenant: Tenant) -> Tenant:
        """Create a new tenant."""
        ...

    async def get(self, tenant_id: UUID) -> Tenant | None:
        """Get tenant by ID."""
        ...

    async def get_by_slug(self, slug: str) -> Tenant | None:
        """Get tenant by slug."""
        ...

    async def update(self, tenant: Tenant) -> Tenant:
        """Update tenant."""
        ...

    async def list(
        self,
        status: TenantStatus | None = None,
        plan: TenantPlan | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Tenant]:
        """List tenants with optional filters."""
        ...

    async def delete(self, tenant_id: UUID) -> bool:
        """Soft delete tenant."""
        ...
