"""Tenant entity."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
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
    monthly_budget_usd: float = 100.0  # Default $100 monthly budget
    daily_budget_usd: float = 10.0  # Default $10 daily budget
    spent_monthly_usd: float = 0.0
    spent_daily_usd: float = 0.0
    budget_reset_at: datetime | None = None
    rate_limit_config: dict[str, int] = field(default_factory=lambda: {"requests_per_minute": 60, "concurrent_runs": 5})

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

    def record_spent(self, amount_usd: float, budget_type: str = "daily") -> None:
        """Record spent amount against tenant budget.

        Args:
            amount_usd: Amount spent in USD
            budget_type: Type of budget to record against ("daily" or "monthly")
        """
        if budget_type == "daily":
            self.spent_daily_usd += amount_usd
        elif budget_type == "monthly":
            self.spent_monthly_usd += amount_usd
        else:
            raise ValueError(f"Invalid budget type: {budget_type}")
        self.touch()

    def has_remaining_budget(self, additional_cost_usd: float, budget_type: str = "daily") -> bool:
        """Check if tenant has remaining budget.

        Args:
            additional_cost_usd: Additional cost to check
            budget_type: Type of budget to check ("daily" or "monthly")

        Returns:
            True if tenant can afford the additional cost, False otherwise
        """
        if budget_type == "daily":
            return (self.spent_daily_usd + additional_cost_usd) <= self.daily_budget_usd
        elif budget_type == "monthly":
            return (self.spent_monthly_usd + additional_cost_usd) <= self.monthly_budget_usd
        else:
            raise ValueError(f"Invalid budget type: {budget_type}")

    def get_remaining_budget(self, budget_type: str = "daily") -> float:
        """Get remaining budget for tenant.

        Args:
            budget_type: Type of budget to get ("daily" or "monthly")

        Returns:
            Remaining budget in USD
        """
        if budget_type == "daily":
            return max(0.0, self.daily_budget_usd - self.spent_daily_usd)
        elif budget_type == "monthly":
            return max(0.0, self.monthly_budget_usd - self.spent_monthly_usd)
        else:
            raise ValueError(f"Invalid budget type: {budget_type}")

    def reset_budget(self, budget_type: str = "daily") -> None:
        """Reset tenant budget tracking.

        Args:
            budget_type: Type of budget to reset ("daily" or "monthly")
        """
        if budget_type == "daily":
            self.spent_daily_usd = 0.0
        elif budget_type == "monthly":
            self.spent_monthly_usd = 0.0
        else:
            raise ValueError(f"Invalid budget type: {budget_type}")
        self.budget_reset_at = datetime.now()
        self.touch()
