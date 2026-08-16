"""Run state value objects."""

from __future__ import annotations

from enum import StrEnum


class RunState(StrEnum):
    """Valid states for a run lifecycle."""

    QUEUED = "queued"
    RUNNING = "running"
    AWAITING_APPROVAL = "awaiting_approval"
    RETRY_SCHEDULED = "retry_scheduled"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"

    @property
    def is_terminal(self) -> bool:
        """Return True if this is a terminal state."""
        return self in {
            RunState.SUCCEEDED,
            RunState.FAILED,
            RunState.CANCELLED,
            RunState.TIMED_OUT,
        }

    @property
    def is_active(self) -> bool:
        """Return True if the run is actively executing."""
        return self in {
            RunState.RUNNING,
            RunState.AWAITING_APPROVAL,
        }

    @property
    def is_queued(self) -> bool:
        """Return True if the run is waiting to be picked up."""
        return self in {
            RunState.QUEUED,
            RunState.RETRY_SCHEDULED,
        }

    def can_transition_to(self, new_state: RunState) -> bool:
        """Check if transition to new_state is valid."""
        valid_transitions: dict[RunState, set[RunState]] = {
            RunState.QUEUED: {
                RunState.RUNNING,
                RunState.CANCELLED,
                RunState.TIMED_OUT,
            },
            RunState.RUNNING: {
                RunState.AWAITING_APPROVAL,
                RunState.SUCCEEDED,
                RunState.FAILED,
                RunState.CANCELLED,
                RunState.TIMED_OUT,
                RunState.RETRY_SCHEDULED,
            },
            RunState.AWAITING_APPROVAL: {
                RunState.RUNNING,
                RunState.FAILED,
                RunState.CANCELLED,
                RunState.TIMED_OUT,
            },
            RunState.RETRY_SCHEDULED: {
                RunState.QUEUED,
                RunState.RUNNING,
                RunState.CANCELLED,
                RunState.TIMED_OUT,
            },
            RunState.SUCCEEDED: set(),
            RunState.FAILED: set(),
            RunState.CANCELLED: set(),
            RunState.TIMED_OUT: set(),
        }
        return new_state in valid_transitions.get(self, set())


class RunStepKind(StrEnum):
    """Types of run steps."""

    MODEL_CALL = "model_call"
    TOOL_CALL = "tool_call"
    MEMORY_READ = "memory_read"
    MEMORY_WRITE = "memory_write"
    APPROVAL_REQUEST = "approval_request"
    CONDITIONAL = "conditional"
    LOOP = "loop"
