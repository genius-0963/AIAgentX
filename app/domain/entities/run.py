"""Run and RunStep entities with state machine."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from app.domain.entities.base import AggregateRoot, Entity
from app.domain.events.run_events import (
    RunCancelled,
    RunCompleted,
    RunCreated,
    RunFailed,
    RunStateChanged,
    RunStepCreated,
    RunTimedOut,
)
from app.domain.value_objects.money import Money, TokenUsage
from app.domain.value_objects.state import RunState, RunStepKind


@dataclass(slots=True, kw_only=True)
class Run(AggregateRoot):
    """Run aggregate root with state machine."""

    tenant_id: UUID
    agent_version_id: UUID
    state: RunState = RunState.QUEUED
    input_data: dict[str, Any] = field(default_factory=dict)
    output_data: dict[str, Any] | None = None
    idempotency_key: str = ""
    attempt: int = 0
    max_steps: int = 100
    max_cost: Money = field(default_factory=lambda: Money(10_000_000))  # $10 default
    spent_cost: Money = field(default_factory=lambda: Money(0))
    timeout_seconds: int = 90  # Default 90 second timeout
    retry_budget: int = 3  # Default retry budget
    lease_owner: str | None = None
    lease_expires_at: datetime | None = None
    cancel_requested_at: datetime | None = None
    idempotency_response: dict[str, Any] | None = None
    _steps: list[RunStep] = field(default_factory=list, init=False, repr=False)

    def __post_init__(self) -> None:
        if not self.idempotency_key:
            raise ValueError("Idempotency key cannot be empty")
        if self.max_steps <= 0:
            raise ValueError("Max steps must be positive")
        if self.max_cost.micro_units <= 0:
            raise ValueError("Max cost must be positive")
        if self.attempt < 0:
            raise ValueError("Attempt cannot be negative")

        self.add_event(
            RunCreated(
                tenant_id=self.tenant_id,
                agent_version_id=self.agent_version_id,
                input_data=self.input_data,
                idempotency_key=self.idempotency_key,
            )
        )

    # State machine transitions
    def _transition(self, new_state: RunState, reason: str | None = None) -> None:
        """Internal state transition with validation."""
        if self.state.is_terminal:
            raise ValueError(f"Cannot transition from terminal state {self.state}")
        if not self.state.can_transition_to(new_state):
            raise ValueError(f"Invalid transition from {self.state} to {new_state}")

        old_state = self.state
        self.state = new_state
        self.touch()
        self.add_event(
            RunStateChanged(
                tenant_id=self.tenant_id,
                agent_version_id=self.agent_version_id,
                old_state=old_state,
                new_state=new_state,
                reason=reason,
            )
        )

    def start(self, lease_owner: str, lease_duration_seconds: int = 300) -> None:
        """Start the run (transition to RUNNING)."""
        self._transition(RunState.RUNNING)
        self.lease_owner = lease_owner
        self.lease_expires_at = datetime.now(UTC).replace(
            second=datetime.now(UTC).second + lease_duration_seconds
        )

    def request_approval(self) -> None:
        """Request approval (transition to AWAITING_APPROVAL)."""
        self._transition(RunState.AWAITING_APPROVAL)

    def resume_from_approval(self) -> None:
        """Resume from approval (transition to RUNNING)."""
        self._transition(RunState.RUNNING)

    def schedule_retry(self) -> None:
        """Schedule retry (transition to RETRY_SCHEDULED)."""
        self._transition(RunState.RETRY_SCHEDULED)
        self.attempt += 1

    def requeue(self) -> None:
        """Requeue for retry (transition to QUEUED)."""
        self._transition(RunState.QUEUED)

    def complete(self, output_data: dict[str, Any]) -> None:
        """Complete successfully (transition to SUCCEEDED)."""
        self._transition(RunState.SUCCEEDED)
        self.output_data = output_data
        self.add_event(
            RunCompleted(
                tenant_id=self.tenant_id,
                agent_version_id=self.agent_version_id,
                output_data=output_data,
                total_cost=self.spent_cost.micro_units,
                steps_count=len(self._steps),
            )
        )

    def fail(self, error: str, failed_step: int | None = None) -> None:
        """Fail the run (transition to FAILED)."""
        self._transition(RunState.FAILED, reason=error)
        self.add_event(
            RunFailed(
                tenant_id=self.tenant_id,
                agent_version_id=self.agent_version_id,
                error=error,
                failed_step=failed_step,
            )
        )

    def cancel(self, reason: str | None = None) -> None:
        """Cancel the run (transition to CANCELLED)."""
        if self.state.is_terminal:
            return  # Idempotent for terminal states
        self.cancel_requested_at = datetime.now(UTC)
        self._transition(RunState.CANCELLED, reason=reason)
        self.add_event(
            RunCancelled(
                tenant_id=self.tenant_id,
                agent_version_id=self.agent_version_id,
                reason=reason,
            )
        )

    def timeout(self) -> None:
        """Timeout the run (transition to TIMED_OUT)."""
        if self.state.is_terminal:
            return  # Idempotent for terminal states
        self._transition(RunState.TIMED_OUT)
        self.add_event(
            RunTimedOut(
                tenant_id=self.tenant_id,
                agent_version_id=self.agent_version_id,
                last_state=self.state,
            )
        )

    def is_lease_valid(self) -> bool:
        """Check if the current lease is still valid."""
        if not self.lease_owner or not self.lease_expires_at:
            return False
        return datetime.now(UTC) < self.lease_expires_at

    def renew_lease(self, lease_owner: str, lease_duration_seconds: int = 300) -> bool:
        """Renew the worker lease."""
        if self.lease_owner != lease_owner:
            return False
        self.lease_expires_at = datetime.now(UTC).replace(
            second=datetime.now(UTC).second + lease_duration_seconds
        )
        self.touch()
        return True

    def add_step(
        self,
        sequence: int,
        kind: RunStepKind,
        input_data: dict[str, Any] | None = None,
    ) -> RunStep:
        """Add a step to the run."""
        if len(self._steps) >= self.max_steps:
            raise ValueError("Max steps exceeded")
        if any(s.sequence == sequence for s in self._steps):
            raise ValueError(f"Step sequence {sequence} already exists")

        step = RunStep(
            run_id=self.id,
            sequence=sequence,
            kind=kind,
            state=RunState.QUEUED,
            input_data=input_data,
        )
        self._steps.append(step)
        self.add_event(
            RunStepCreated(
                run_id=self.id,
                sequence=sequence,
                kind=kind.value,
                input_data=input_data,
            )
        )
        return step

    def get_step(self, sequence: int) -> RunStep | None:
        """Get a step by sequence."""
        return next((s for s in self._steps if s.sequence == sequence), None)

    def record_cost(self, cost: Money) -> None:
        """Record cost against the run budget."""
        new_total = self.spent_cost + cost
        if new_total > self.max_cost:
            raise ValueError("Run would exceed max cost")
        self.spent_cost = new_total
        self.touch()

    def record_token_usage(self, usage: TokenUsage, provider: str = "", model: str = "") -> None:
        """Record token usage (for cost tracking).

        Args:
            usage: Token usage information
            provider: Provider name (e.g., 'openai')
            model: Model name (e.g., 'gpt-4o')
        """
        # For now, use the simple cost model
        # In the future, this will use the CostService for accurate pricing
        cost_micro = (usage.total_tokens * 10) // 1000
        if cost_micro > 0:
            self.record_cost(Money(cost_micro))

        # The detailed usage tracking will be handled at the step level
        # through the UsageRepository

    def can_execute(self) -> bool:
        """Check if run can execute."""
        return self.state in {RunState.QUEUED, RunState.RUNNING, RunState.RETRY_SCHEDULED}

    def has_remaining_budget(self, additional_cost: Money) -> bool:
        """Check if run has remaining budget for additional cost.

        Args:
            additional_cost: Additional cost to check against budget

        Returns:
            True if run can afford the additional cost, False otherwise
        """
        return (self.spent_cost + additional_cost) <= self.max_cost

    def has_remaining_steps(self) -> bool:
        """Check if run has remaining steps.

        Returns:
            True if run has remaining steps, False otherwise
        """
        return len(self._steps) < self.max_steps

    def has_remaining_time(self) -> bool:
        """Check if run has remaining time before timeout.

        Returns:
            True if run has remaining time, False otherwise
        """
        elapsed_seconds = (datetime.now(UTC) - self.created_at).total_seconds()
        return elapsed_seconds < self.timeout_seconds

    def has_remaining_retries(self) -> bool:
        """Check if run has remaining retry budget.

        Returns:
            True if run has remaining retries, False otherwise
        """
        return self.attempt < self.retry_budget

    def get_remaining_budget(self) -> Money:
        """Get remaining budget for the run.

        Returns:
            Remaining budget as Money value object
        """
        return self.max_cost - self.spent_cost

    def get_remaining_steps(self) -> int:
        """Get remaining steps for the run.

        Returns:
            Number of remaining steps
        """
        return self.max_steps - len(self._steps)

    def get_remaining_time(self) -> float:
        """Get remaining time in seconds before timeout.

        Returns:
            Remaining time in seconds
        """
        elapsed_seconds = (datetime.now(UTC) - self.created_at).total_seconds()
        return max(0.0, self.timeout_seconds - elapsed_seconds)


@dataclass(slots=True, kw_only=True)
class RunStep(Entity):
    """Run step entity (part of Run aggregate)."""

    run_id: UUID
    sequence: int
    kind: RunStepKind
    state: RunState = RunState.QUEUED
    input_data: dict[str, Any] | None = None
    output_data: dict[str, Any] | None = None
    error: str | None = None

    def __post_init__(self) -> None:
        if self.sequence < 0:
            raise ValueError("Sequence must be non-negative")

    def start(self) -> None:
        """Start the step."""
        if self.state != RunState.QUEUED:
            raise ValueError(f"Cannot start step in state {self.state}")
        self.state = RunState.RUNNING
        self.touch()

    def complete(self, output_data: dict[str, Any]) -> None:
        """Complete the step."""
        if self.state != RunState.RUNNING:
            raise ValueError(f"Cannot complete step in state {self.state}")
        self.state = RunState.SUCCEEDED
        self.output_data = output_data
        self.touch()

    def fail(self, error: str) -> None:
        """Fail the step."""
        if self.state not in {RunState.QUEUED, RunState.RUNNING}:
            raise ValueError(f"Cannot fail step in state {self.state}")
        self.state = RunState.FAILED
        self.error = error
        self.touch()
