"""Base domain event classes."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Generic, TypeVar
from uuid import UUID, uuid4

T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class DomainEvent(Generic[T]):
    """Base domain event."""

    event_type: str
    aggregate_id: UUID
    payload: T
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    event_id: UUID = field(default_factory=uuid4)

    @classmethod
    def create(cls, aggregate_id: UUID, payload: T) -> DomainEvent[T]:
        """Factory method to create event with auto-generated fields."""
        return cls(
            event_type=cls.__name__,
            aggregate_id=aggregate_id,
            payload=payload,
        )


class EventPublisher:
    """In-memory event publisher for domain events."""

    def __init__(self) -> None:
        self._handlers: dict[str, list[EventHandler]] = {}

    def subscribe(self, event_type: str, handler: EventHandler) -> None:
        """Subscribe a handler to an event type."""
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)

    def publish(self, event: DomainEvent[Any]) -> None:
        """Publish an event to all subscribed handlers."""
        handlers = self._handlers.get(event.event_type, [])
        for handler in handlers:
            handler.handle(event)


class EventHandler(ABC):
    """Base event handler."""

    @abstractmethod
    def handle(self, event: DomainEvent[Any]) -> None:
        """Handle a domain event."""
        pass
