"""Degradation-related domain events."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from app.domain.events.base import DomainEvent


@dataclass(frozen=True, slots=True)
class DegradationEntered(DomainEvent):
    """Emitted when system enters a degradation mode."""

    mode: str
    reason: str
    affected_components: list[str]
    entered_at: datetime

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_type": "degradation_entered",
            "mode": self.mode,
            "reason": self.reason,
            "affected_components": self.affected_components,
            "entered_at": self.entered_at.isoformat(),
            "timestamp": datetime.now(UTC).isoformat(),
        }


@dataclass(frozen=True, slots=True)
class DegradationExited(DomainEvent):
    """Emitted when system exits a degradation mode."""

    previous_mode: str
    recovered_at: datetime
    recovery_duration_seconds: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_type": "degradation_exited",
            "previous_mode": self.previous_mode,
            "recovered_at": self.recovered_at.isoformat(),
            "recovery_duration_seconds": self.recovery_duration_seconds,
            "timestamp": datetime.now(UTC).isoformat(),
        }


@dataclass(frozen=True, slots=True)
class DegradationComponentFailed(DomainEvent):
    """Emitted when a component fails triggering degradation."""

    component: str
    failure_count: int
    threshold: int
    failed_at: datetime

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_type": "degradation_component_failed",
            "component": self.component,
            "failure_count": self.failure_count,
            "threshold": self.threshold,
            "failed_at": self.failed_at.isoformat(),
            "timestamp": datetime.now(UTC).isoformat(),
        }


@dataclass(frozen=True, slots=True)
class DegradationComponentRecovered(DomainEvent):
    """Emitted when a component recovers from failure."""

    component: str
    recovered_at: datetime

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_type": "degradation_component_recovered",
            "component": self.component,
            "recovered_at": self.recovered_at.isoformat(),
            "timestamp": datetime.now(UTC).isoformat(),
        }
