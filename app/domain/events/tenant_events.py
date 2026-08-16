"""Tenant domain events."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, slots=True)
class TenantCreated:
    """Event fired when a tenant is created."""

    tenant_id: UUID
    slug: str
    plan: str


@dataclass(frozen=True, slots=True)
class TenantSuspended:
    """Event fired when a tenant is suspended."""

    tenant_id: UUID
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class TenantActivated:
    """Event fired when a tenant is activated."""

    tenant_id: UUID


@dataclass(frozen=True, slots=True)
class TenantDeleted:
    """Event fired when a tenant is deleted (soft)."""

    tenant_id: UUID
