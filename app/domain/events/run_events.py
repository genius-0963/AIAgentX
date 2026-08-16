"""Run domain events."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from app.domain.value_objects.state import RunState


@dataclass(frozen=True, slots=True)
class RunCreated:
    """Event fired when a run is created."""

    tenant_id: UUID
    agent_version_id: UUID
    input_data: dict[str, Any]
    idempotency_key: str


@dataclass(frozen=True, slots=True)
class RunStateChanged:
    """Event fired when run state changes."""

    tenant_id: UUID
    agent_version_id: UUID
    old_state: RunState
    new_state: RunState
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class RunStepCreated:
    """Event fired when a run step is created."""

    run_id: UUID
    sequence: int
    kind: str
    input_data: dict[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class RunCompleted:
    """Event fired when run completes successfully."""

    tenant_id: UUID
    agent_version_id: UUID
    output_data: dict[str, Any]
    total_cost: int
    steps_count: int


@dataclass(frozen=True, slots=True)
class RunFailed:
    """Event fired when run fails."""

    tenant_id: UUID
    agent_version_id: UUID
    error: str
    failed_step: int | None = None


@dataclass(frozen=True, slots=True)
class RunCancelled:
    """Event fired when run is cancelled."""

    tenant_id: UUID
    agent_version_id: UUID
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class RunTimedOut:
    """Event fired when run times out."""

    tenant_id: UUID
    agent_version_id: UUID
    last_state: RunState
