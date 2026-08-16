"""Run repository protocol."""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from app.domain.entities.run import Run, RunStep
from app.domain.value_objects.state import RunState


class RunRepository(Protocol):
    """Repository for run operations."""

    async def create(self, run: Run) -> Run:
        """Create a new run."""
        ...

    async def get(self, run_id: UUID) -> Run | None:
        """Get run by ID with steps."""
        ...

    async def get_by_idempotency_key(self, tenant_id: UUID, key: str) -> Run | None:
        """Get run by idempotency key."""
        ...

    async def update(self, run: Run) -> Run:
        """Update run."""
        ...

    async def list(
        self,
        tenant_id: UUID,
        state: RunState | None = None,
        agent_version_id: UUID | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Run]:
        """List runs for tenant with filters."""
        ...

    async def get_queued_runs(
        self,
        tenant_id: UUID | None = None,
        limit: int = 100,
    ) -> list[Run]:
        """Get runs ready for execution."""
        ...

    async def get_running_runs(
        self,
        tenant_id: UUID | None = None,
        limit: int = 100,
    ) -> list[Run]:
        """Get currently running runs."""
        ...

    # Step operations
    async def add_step(self, step: RunStep) -> RunStep:
        """Add a step to a run."""
        ...

    async def get_step(self, run_id: UUID, sequence: int) -> RunStep | None:
        """Get step by sequence."""
        ...

    async def update_step(self, step: RunStep) -> RunStep:
        """Update step."""
        ...

    async def list_steps(self, run_id: UUID) -> list[RunStep]:
        """List all steps for a run."""
        ...
