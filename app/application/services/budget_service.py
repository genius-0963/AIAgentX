"""Budget enforcement service for cost control and resource limits."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID

from app.domain.events.budget_events import (
    BudgetExceeded,
    BudgetWarning,
    CostRecorded,
    StepLimitExceeded,
    TenantBudgetExceeded,
    TimeoutExceeded,
)
from app.domain.repositories.run import RunRepository
from app.domain.repositories.tenant import TenantRepository
from app.domain.value_objects.money import Money
from app.infrastructure.observability.logging import get_logger

if TYPE_CHECKING:
    from app.application.services.cost_service import CostService

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class BudgetCheckResult:
    """Result of a budget check."""

    allowed: bool
    reason: str | None = None
    warning: str | None = None
    remaining_budget: Money = Money(0)
    remaining_steps: int = 0
    remaining_seconds: float = 0.0


class BudgetService:
    """Service for budget enforcement and cost tracking."""

    def __init__(
        self,
        run_repository: RunRepository,
        tenant_repository: TenantRepository,
        cost_service: CostService,
        warning_threshold_percent: float = 80.0,
    ) -> None:
        """Initialize budget service.

        Args:
            run_repository: Run repository for accessing run data
            tenant_repository: Tenant repository for accessing tenant data
            cost_service: Cost service for calculating costs
            warning_threshold_percent: Percentage at which to emit budget warnings
        """
        self._run_repository = run_repository
        self._tenant_repository = tenant_repository
        self._cost_service = cost_service
        self._warning_threshold_percent = warning_threshold_percent

    async def check_run_budget(
        self,
        run_id: UUID,
        additional_cost: Money,
    ) -> BudgetCheckResult:
        """Check if a run can proceed based on its budget constraints.

        Args:
            run_id: Run ID to check
            additional_cost: Additional cost that would be incurred

        Returns:
            BudgetCheckResult with allowance status and details
        """
        run = await self._run_repository.get(run_id)
        if not run:
            logger.warning("Run not found for budget check", extra={"run_id": str(run_id)})
            return BudgetCheckResult(allowed=False, reason="Run not found")

        # Check cost limit
        new_total = run.spent_cost + additional_cost
        if new_total > run.max_cost:
            logger.warning(
                "Run would exceed max cost",
                extra={
                    "run_id": str(run_id),
                    "max_cost": str(run.max_cost),
                    "spent_cost": str(run.spent_cost),
                    "additional_cost": str(additional_cost),
                },
            )
            run.add_event(
                BudgetExceeded(
                    run_id=run.id,
                    tenant_id=run.tenant_id,
                    max_cost_microunits=run.max_cost.micro_units,
                    spent_cost_microunits=run.spent_cost.micro_units,
                    additional_cost_microunits=additional_cost.micro_units,
                )
            )
            return BudgetCheckResult(
                allowed=False,
                reason="Run would exceed maximum cost limit",
                remaining_budget=run.max_cost - run.spent_cost,
            )

        # Check for budget warning
        usage_percent = (run.spent_cost.micro_units / run.max_cost.micro_units) * 100
        if usage_percent >= self._warning_threshold_percent:
            run.add_event(
                BudgetWarning(
                    run_id=run.id,
                    tenant_id=run.tenant_id,
                    max_cost_microunits=run.max_cost.micro_units,
                    spent_cost_microunits=run.spent_cost.micro_units,
                    warning_threshold_percent=self._warning_threshold_percent,
                )
            )
            logger.info(
                "Budget warning threshold reached",
                extra={
                    "run_id": str(run_id),
                    "usage_percent": usage_percent,
                    "threshold": self._warning_threshold_percent,
                },
            )

        # Check step limit
        current_steps = len(run._steps)
        if current_steps >= run.max_steps:
            logger.warning(
                "Run would exceed step limit",
                extra={
                    "run_id": str(run_id),
                    "max_steps": run.max_steps,
                    "current_steps": current_steps,
                },
            )
            run.add_event(
                StepLimitExceeded(
                    run_id=run.id,
                    tenant_id=run.tenant_id,
                    max_steps=run.max_steps,
                    current_step=current_steps,
                )
            )
            return BudgetCheckResult(
                allowed=False,
                reason="Run would exceed maximum step limit",
                remaining_steps=0,
            )

        # Check timeout
        elapsed_seconds = (datetime.now(UTC) - run.created_at).total_seconds()
        timeout_seconds = getattr(run, "timeout_seconds", 90)  # Default 90 seconds
        if elapsed_seconds > timeout_seconds:
            logger.warning(
                "Run would exceed timeout",
                extra={
                    "run_id": str(run_id),
                    "timeout_seconds": timeout_seconds,
                    "elapsed_seconds": elapsed_seconds,
                },
            )
            run.add_event(
                TimeoutExceeded(
                    run_id=run.id,
                    tenant_id=run.tenant_id,
                    timeout_seconds=timeout_seconds,
                    elapsed_seconds=int(elapsed_seconds),
                )
            )
            return BudgetCheckResult(
                allowed=False,
                reason="Run would exceed timeout limit",
                remaining_seconds=0.0,
            )

        return BudgetCheckResult(
            allowed=True,
            remaining_budget=run.max_cost - new_total,
            remaining_steps=run.max_steps - current_steps,
            remaining_seconds=timeout_seconds - elapsed_seconds,
        )

    async def check_tenant_budget(
        self,
        tenant_id: UUID,
        additional_cost: Money,
        budget_type: str = "daily",
    ) -> BudgetCheckResult:
        """Check if a tenant can proceed based on its budget constraints.

        Args:
            tenant_id: Tenant ID to check
            additional_cost: Additional cost that would be incurred
            budget_type: Type of budget to check ("daily" or "monthly")

        Returns:
            BudgetCheckResult with allowance status and details
        """
        tenant = await self._tenant_repository.get(tenant_id)
        if not tenant:
            logger.warning("Tenant not found for budget check", extra={"tenant_id": str(tenant_id)})
            return BudgetCheckResult(allowed=False, reason="Tenant not found")

        # Get tenant budget limits (these will be added to tenant entity)
        max_budget = getattr(tenant, f"{budget_type}_budget_usd", 100.0)  # Default $100
        spent_budget = getattr(tenant, f"spent_{budget_type}_usd", 0.0)

        new_total = spent_budget + (additional_cost.micro_units / 1_000_000)
        if new_total > max_budget:
            logger.warning(
                "Tenant would exceed budget",
                extra={
                    "tenant_id": str(tenant_id),
                    "budget_type": budget_type,
                    "max_budget": max_budget,
                    "spent_budget": spent_budget,
                    "additional_cost": additional_cost.to_decimal(),
                },
            )
            tenant.add_event(
                TenantBudgetExceeded(
                    tenant_id=tenant.id,
                    budget_type=budget_type,
                    max_budget_usd=max_budget,
                    spent_budget_usd=spent_budget,
                    additional_cost_usd=additional_cost.to_decimal(),
                )
            )
            return BudgetCheckResult(
                allowed=False,
                reason=f"Tenant would exceed {budget_type} budget limit",
                remaining_budget=Money(int((max_budget - spent_budget) * 1_000_000)),
            )

        return BudgetCheckResult(
            allowed=True,
            remaining_budget=Money(int((max_budget - new_total) * 1_000_000)),
        )

    async def record_spent(
        self,
        run_id: UUID,
        cost: Money,
        provider: str = "",
        model: str = "",
    ) -> None:
        """Record spent cost against a run.

        Args:
            run_id: Run ID to record cost against
            cost: Cost to record
            provider: Provider name for tracking
            model: Model name for tracking
        """
        run = await self._run_repository.get(run_id)
        if not run:
            logger.warning("Run not found for cost recording", extra={"run_id": str(run_id)})
            return

        try:
            run.record_cost(cost)
            await self._run_repository.update(run)

            run.add_event(
                CostRecorded(
                    run_id=run.id,
                    tenant_id=run.tenant_id,
                    cost_microunits=cost.micro_units,
                    total_spent_microunits=run.spent_cost.micro_units,
                    provider=provider,
                    model=model,
                )
            )

            logger.info(
                "Cost recorded successfully",
                extra={
                    "run_id": str(run_id),
                    "cost_usd": cost.to_decimal(),
                    "total_spent_usd": run.spent_cost.to_decimal(),
                    "provider": provider,
                    "model": model,
                },
            )
        except ValueError as e:
            logger.error(
                "Failed to record cost - would exceed budget",
                extra={"run_id": str(run_id), "cost": str(cost), "error": str(e)},
            )
            raise

    async def record_provider_usage(
        self,
        run_id: UUID,
        provider: str,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
    ) -> None:
        """Record provider usage and calculate cost.

        Args:
            run_id: Run ID to record usage against
            provider: Provider name
            model: Model name
            prompt_tokens: Number of prompt tokens
            completion_tokens: Number of completion tokens
        """
        cost_micro = self._cost_service.calculate_cost(
            provider, model, prompt_tokens, completion_tokens
        )
        if cost_micro > 0:
            await self.record_spent(run_id, Money(cost_micro), provider, model)

    async def check_step_limit(self, run_id: UUID) -> bool:
        """Check if a run has remaining steps.

        Args:
            run_id: Run ID to check

        Returns:
            True if run has remaining steps, False otherwise
        """
        run = await self._run_repository.get(run_id)
        if not run:
            return False

        current_steps = len(run._steps)
        return current_steps < run.max_steps

    async def check_timeout(self, run_id: UUID) -> bool:
        """Check if a run has remaining time.

        Args:
            run_id: Run ID to check

        Returns:
            True if run has remaining time, False otherwise
        """
        run = await self._run_repository.get(run_id)
        if not run:
            return False

        elapsed_seconds = (datetime.now(UTC) - run.created_at).total_seconds()
        timeout_seconds = getattr(run, "timeout_seconds", 90)
        return elapsed_seconds <= timeout_seconds

    async def get_remaining_budget(self, run_id: UUID) -> Money:
        """Get remaining budget for a run.

        Args:
            run_id: Run ID to check

        Returns:
            Remaining budget as Money value object
        """
        run = await self._run_repository.get(run_id)
        if not run:
            return Money(0)

        return run.max_cost - run.spent_cost

    async def reset_tenant_budget(
        self,
        tenant_id: UUID,
        budget_type: str = "daily",
    ) -> None:
        """Reset tenant budget tracking (typically called by scheduled job).

        Args:
            tenant_id: Tenant ID to reset
            budget_type: Type of budget to reset ("daily" or "monthly")
        """
        tenant = await self._tenant_repository.get(tenant_id)
        if not tenant:
            logger.warning("Tenant not found for budget reset", extra={"tenant_id": str(tenant_id)})
            return

        # Reset the spent budget field
        setattr(tenant, f"spent_{budget_type}_usd", 0.0)
        tenant.budget_reset_at = datetime.now(UTC)
        await self._tenant_repository.update(tenant)

        logger.info(
            "Tenant budget reset",
            extra={"tenant_id": str(tenant_id), "budget_type": budget_type},
        )
