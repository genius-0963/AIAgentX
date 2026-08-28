"""Tenant entity."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum

from app.domain.entities.base import AggregateRoot


class TenantStatus(StrEnum):
    """Tenant status values."""

    ACTIVE = "active"
    SUSPENDED = "suspended"
    DELETED = "deleted"


class TenantPlan(StrEnum):
    """Tenant plan tiers."""

    FREE = "free"
    STARTER = "starter"
    PROFESSIONAL = "professional"
    ENTERPRISE = "enterprise"


@dataclass(slots=True, kw_only=True)
class Tenant(AggregateRoot):
    """Tenant aggregate root."""

    slug: str
    plan: TenantPlan = TenantPlan.FREE
    status: TenantStatus = TenantStatus.ACTIVE
    daily_budget_usd: float = 100.0
    monthly_budget_usd: float = 1000.0
    spent_daily_usd: float = 0.0
    spent_monthly_usd: float = 0.0
    budget_reset_at: datetime | None = None

    def __post_init__(self) -> None:
        if not self.slug or not self.slug.strip():
            raise ValueError("Slug cannot be empty")
        if len(self.slug) > 100:
            raise ValueError("Slug too long (max 100 characters)")
        if not self.slug.islower() or not self.slug.replace("-", "").isalnum():
            raise ValueError("Slug must be lowercase alphanumeric with hyphens")

    def suspend(self, reason: str | None = None) -> None:
        """Suspend the tenant."""
        if self.status == TenantStatus.DELETED:
            raise ValueError("Cannot suspend deleted tenant")
        if self.status == TenantStatus.SUSPENDED:
            return  # Idempotent
        self.status = TenantStatus.SUSPENDED
        self.touch()
        self.add_event({"type": "TenantSuspended", "tenant_id": self.id, "reason": reason})

    def activate(self) -> None:
        """Activate the tenant."""
        if self.status == TenantStatus.DELETED:
            raise ValueError("Cannot activate deleted tenant")
        if self.status == TenantStatus.ACTIVE:
            return  # Idempotent
        self.status = TenantStatus.ACTIVE
        self.touch()
        self.add_event({"type": "TenantActivated", "tenant_id": self.id})

    def soft_delete(self) -> None:
        """Soft delete the tenant."""
        if self.status == TenantStatus.DELETED:
            return  # Idempotent
        self.status = TenantStatus.DELETED
        self.touch()
        self.add_event({"type": "TenantDeleted", "tenant_id": self.id})

    def can_create_runs(self) -> bool:
        """Check if tenant can create new runs."""
        return self.status == TenantStatus.ACTIVE

    def change_plan(self, plan: TenantPlan) -> None:
        """Change tenant plan."""
        if self.status == TenantStatus.DELETED:
            raise ValueError("Cannot change plan for deleted tenant")
        self.plan = plan
        self.touch()
