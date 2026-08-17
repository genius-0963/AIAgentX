"""Run use cases."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any
from uuid import UUID

from app.domain.entities.run import Run
from app.domain.repositories.run import RunRepository


class RunUseCases:
    """Use cases for run management."""

    def __init__(self, repository: RunRepository) -> None:
        self._repository = repository

    async def create_run(
        self,
        tenant_id: UUID,
        agent_version_id: UUID,
        input_data: dict[str, Any],
        idempotency_key: str,
        max_steps: int = 100,
        max_cost_usd: float = 10.0,
        session_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Run:
        """Create a new run.

        Args:
            tenant_id: Tenant ID
            agent_version_id: Agent version ID to use
            input_data: Input data for the run
            idempotency_key: Idempotency key for duplicate prevention
            max_steps: Maximum number of steps
            max_cost_usd: Maximum cost in USD
            session_id: Optional session ID
            metadata: Optional metadata

        Returns:
            Created run entity

        Raises:
            ValueError: If validation fails
        """
        # Check for existing run with same idempotency key
        existing = await self._repository.get_by_idempotency_key(tenant_id, idempotency_key)
        if existing:
            return existing

        # Create new run
        from app.domain.value_objects.money import Money

        run = Run(
            tenant_id=tenant_id,
            agent_version_id=agent_version_id,
            input_data=input_data,
            idempotency_key=idempotency_key,
            max_steps=max_steps,
            max_cost=Money(int(max_cost_usd * 1_000_000)),  # Convert to microunits
        )

        return await self._repository.create(run)

    async def get_run(self, run_id: UUID, tenant_id: UUID) -> Run | None:
        """Get run by ID with tenant check.

        Args:
            run_id: Run ID
            tenant_id: Tenant ID for access control

        Returns:
            Run entity if found and tenant matches, None otherwise
        """
        run = await self._repository.get(run_id)
        if run and run.tenant_id == tenant_id:
            return run
        return None

    async def list_runs(
        self,
        tenant_id: UUID,
        state: str | None = None,
        agent_version_id: UUID | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Sequence[Run]:
        """List runs for tenant with filters.

        Args:
            tenant_id: Tenant ID
            state: Optional state filter
            agent_version_id: Optional agent version filter
            limit: Maximum number of results
            offset: Result offset for pagination

        Returns:
            Sequence of run entities
        """
        from app.domain.value_objects.state import RunState

        state_filter = RunState(state) if state else None
        return await self._repository.list(
            tenant_id=tenant_id,
            state=state_filter,
            agent_version_id=agent_version_id,
            limit=limit,
            offset=offset,
        )

    async def cancel_run(self, run_id: UUID, tenant_id: UUID, reason: str | None = None) -> Run | None:
        """Request cancellation of a run.

        Args:
            run_id: Run ID
            tenant_id: Tenant ID for access control
            reason: Optional cancellation reason

        Returns:
            Updated run entity if found and tenant matches, None otherwise
        """
        run = await self.get_run(run_id, tenant_id)
        if not run:
            return None

        run.cancel(reason=reason)
        return await self._repository.update(run)

    async def get_run_status(self, run_id: UUID, tenant_id: UUID) -> dict[str, Any] | None:
        """Get run status with usage summary.

        Args:
            run_id: Run ID
            tenant_id: Tenant ID for access control

        Returns:
            Dictionary with run status and usage information
        """
        run = await self.get_run(run_id, tenant_id)
        if not run:
            return None

        # Calculate detailed usage from steps
        total_tokens = 0
        provider_usage = {}

        for step in run._steps:
            if hasattr(step, "total_tokens") and step.total_tokens:
                total_tokens += step.total_tokens
            if hasattr(step, "provider") and step.provider:
                provider = step.provider
                if provider not in provider_usage:
                    provider_usage[provider] = {"tokens": 0, "cost": 0}
                provider_usage[provider]["tokens"] += getattr(step, "total_tokens", 0)
                provider_usage[provider]["cost"] += getattr(step, "cost_microunits", 0)

        return {
            "id": str(run.id),
            "tenant_id": str(run.tenant_id),
            "agent_version_id": str(run.agent_version_id),
            "state": run.state.value,
            "input": run.input_data,
            "output": run.output_data,
            "usage": {
                "steps_completed": len(run._steps),
                "total_cost_usd": run.spent_cost.micro_units / 1_000_000,
                "tokens_used": total_tokens,
                "by_provider": provider_usage,
            },
            "attempt": run.attempt,
            "max_steps": run.max_steps,
            "created_at": run.created_at.isoformat(),
            "updated_at": run.updated_at.isoformat(),
            "cancel_requested_at": run.cancel_requested_at.isoformat() if run.cancel_requested_at else None,
        }
