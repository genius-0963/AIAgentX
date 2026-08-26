"""Base entity and aggregate root classes."""

from __future__ import annotations

from abc import ABC
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4


@dataclass(slots=True, kw_only=True)
class Entity(ABC):
    """Base entity with identity."""

    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Entity):
            return NotImplemented
        return self.id == other.id

    def __hash__(self) -> int:
        return hash(self.id)

    def touch(self) -> None:
        """Update the updated_at timestamp."""
        self.updated_at = datetime.now(UTC)


@dataclass(slots=True, kw_only=True)
class AggregateRoot(Entity):
    """Aggregate root that can publish domain events."""

    _events: list[Any] = field(default_factory=list, init=False, repr=False)

    def add_event(self, event: Any) -> None:
        """Add a domain event to be published."""
        self._events.append(event)

    def collect_events(self) -> list[Any]:
        """Collect and clear pending events."""
        events = self._events.copy()
        self._events.clear()
        return events
