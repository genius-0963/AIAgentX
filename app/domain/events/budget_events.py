"""Budget-related domain events."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID


@dataclass(frozen=True, slots=True)
class BudgetExceeded:
    """Emitted when a run exceeds its budget limit."""

    run_id: UUID
    tenant_id: UUID
    max_cost_microunits: int
    spent_cost_microunits: int
    additional_cost_microunits: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_type": "budget_exceeded",
            "run_id": str(self.run_id),
            "tenant_id": str(self.tenant_id),
            "max_cost_usd": self.max_cost_microunits / 1_000_000,
            "spent_cost_usd": self.spent_cost_microunits / 1_000_000,
            "additional_cost_usd": self.additional_cost_microunits / 1_000_000,
            "timestamp": datetime.utcnow().isoformat(),
        }


@dataclass(frozen=True, slots=True)
class StepLimitExceeded:
    """Emitted when a run exceeds its step limit."""

    run_id: UUID
    tenant_id: UUID
    max_steps: int
    current_step: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_type": "step_limit_exceeded",
            "run_id": str(self.run_id),
            "tenant_id": str(self.tenant_id),
            "max_steps": self.max_steps,
            "current_step": self.current_step,
            "timestamp": datetime.utcnow().isoformat(),
        }


@dataclass(frozen=True, slots=True)
class TimeoutExceeded:
    """Emitted when a run exceeds its time limit."""

    run_id: UUID
    tenant_id: UUID
    timeout_seconds: int
    elapsed_seconds: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_type": "timeout_exceeded",
            "run_id": str(self.run_id),
            "tenant_id": str(self.tenant_id),
            "timeout_seconds": self.timeout_seconds,
            "elapsed_seconds": self.elapsed_seconds,
            "timestamp": datetime.utcnow().isoformat(),
        }


@dataclass(frozen=True, slots=True)
class TenantBudgetExceeded:
    """Emitted when a tenant exceeds its budget limit."""

    tenant_id: UUID
    budget_type: str  # "daily" or "monthly"
    max_budget_usd: float
    spent_budget_usd: float
    additional_cost_usd: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_type": "tenant_budget_exceeded",
            "tenant_id": str(self.tenant_id),
            "budget_type": self.budget_type,
            "max_budget_usd": self.max_budget_usd,
            "spent_budget_usd": self.spent_budget_usd,
            "additional_cost_usd": self.additional_cost_usd,
            "timestamp": datetime.utcnow().isoformat(),
        }


@dataclass(frozen=True, slots=True)
class BudgetWarning:
    """Emitted when a run approaches its budget limit (warning threshold)."""

    run_id: UUID
    tenant_id: UUID
    max_cost_microunits: int
    spent_cost_microunits: int
    warning_threshold_percent: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_type": "budget_warning",
            "run_id": str(self.run_id),
            "tenant_id": str(self.tenant_id),
            "max_cost_usd": self.max_cost_microunits / 1_000_000,
            "spent_cost_usd": self.spent_cost_microunits / 1_000_000,
            "usage_percent": (self.spent_cost_microunits / self.max_cost_microunits) * 100,
            "warning_threshold_percent": self.warning_threshold_percent,
            "timestamp": datetime.utcnow().isoformat(),
        }


@dataclass(frozen=True, slots=True)
class CostRecorded:
    """Emitted when cost is successfully recorded against a run."""

    run_id: UUID
    tenant_id: UUID
    cost_microunits: int
    total_spent_microunits: int
    provider: str
    model: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_type": "cost_recorded",
            "run_id": str(self.run_id),
            "tenant_id": str(self.tenant_id),
            "cost_usd": self.cost_microunits / 1_000_000,
            "total_spent_usd": self.total_spent_microunits / 1_000_000,
            "provider": self.provider,
            "model": self.model,
            "timestamp": datetime.utcnow().isoformat(),
        }
