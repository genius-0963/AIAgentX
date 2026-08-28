"""Cancellation-related domain events."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID


@dataclass(frozen=True, slots=True)
class CancellationRequested:
    """Emitted when cancellation is requested for a run."""

    run_id: UUID
    tenant_id: UUID
    reason: str | None
    requested_at: datetime

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_type": "cancellation_requested",
            "run_id": str(self.run_id),
            "tenant_id": str(self.tenant_id),
            "reason": self.reason,
            "requested_at": self.requested_at.isoformat(),
            "timestamp": datetime.now(UTC).isoformat(),
        }


@dataclass(frozen=True, slots=True)
class CancellationAcknowledged:
    """Emitted when a worker acknowledges a cancellation request."""

    run_id: UUID
    tenant_id: UUID
    worker_id: str
    acknowledged_at: datetime

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_type": "cancellation_acknowledged",
            "run_id": str(self.run_id),
            "tenant_id": str(self.tenant_id),
            "worker_id": self.worker_id,
            "acknowledged_at": self.acknowledged_at.isoformat(),
            "timestamp": datetime.now(UTC).isoformat(),
        }


@dataclass(frozen=True, slots=True)
class CancellationCompleted:
    """Emitted when cancellation is successfully completed."""

    run_id: UUID
    tenant_id: UUID
    worker_id: str
    completed_at: datetime
    steps_cancelled: int
    cleanup_performed: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_type": "cancellation_completed",
            "run_id": str(self.run_id),
            "tenant_id": str(self.tenant_id),
            "worker_id": self.worker_id,
            "completed_at": self.completed_at.isoformat(),
            "steps_cancelled": self.steps_cancelled,
            "cleanup_performed": self.cleanup_performed,
            "timestamp": datetime.now(UTC).isoformat(),
        }


@dataclass(frozen=True, slots=True)
class CancellationTimeout:
    """Emitted when cancellation does not complete within timeout."""

    run_id: UUID
    tenant_id: UUID
    timeout_seconds: int
    timed_out_at: datetime

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_type": "cancellation_timeout",
            "run_id": str(self.run_id),
            "tenant_id": str(self.tenant_id),
            "timeout_seconds": self.timeout_seconds,
            "timed_out_at": self.timed_out_at.isoformat(),
            "timestamp": datetime.now(UTC).isoformat(),
        }


@dataclass(frozen=True, slots=True)
class CancellationSignal:
    """Emitted when a cancellation signal is sent via Redis pub/sub."""

    run_id: UUID
    tenant_id: UUID
    signal_type: str  # "request", "ack", "complete"
    payload: dict[str, Any] | None
    sent_at: datetime

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_type": "cancellation_signal",
            "run_id": str(self.run_id),
            "tenant_id": str(self.tenant_id),
            "signal_type": self.signal_type,
            "payload": self.payload,
            "sent_at": self.sent_at.isoformat(),
            "timestamp": datetime.now(UTC).isoformat(),
        }
