"""Memory-related domain events."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.domain.events.base import DomainEvent


@dataclass(frozen=True, slots=True)
class MemoryWrittenEvent(DomainEvent[dict]):
    """Event raised when memory is written."""

    event_type: str = "MemoryWrittenEvent"


@dataclass(frozen=True, slots=True)
class MemoryRetrievedEvent(DomainEvent[dict]):
    """Event raised when memory is retrieved."""

    event_type: str = "MemoryRetrievedEvent"


@dataclass(frozen=True, slots=True)
class MemoryExpiredEvent(DomainEvent[dict]):
    """Event raised when memory expires."""

    event_type: str = "MemoryExpiredEvent"


@dataclass(frozen=True, slots=True)
class MemoryCleanupEvent(DomainEvent[dict]):
    """Event raised when memory is cleaned up."""

    event_type: str = "MemoryCleanupEvent"


@dataclass(frozen=True, slots=True)
class SessionCreatedEvent(DomainEvent[dict]):
    """Event raised when a session is created."""

    event_type: str = "SessionCreatedEvent"


@dataclass(frozen=True, slots=True)
class SessionExpiredEvent(DomainEvent[dict]):
    """Event raised when a session expires."""

    event_type: str = "SessionExpiredEvent"


@dataclass(frozen=True, slots=True)
class MemoryAccessDeniedEvent(DomainEvent[dict]):
    """Event raised when memory access is denied."""

    event_type: str = "MemoryAccessDeniedEvent"


@dataclass(frozen=True, slots=True)
class RetentionPolicyChangedEvent(DomainEvent[dict]):
    """Event raised when retention policy changes."""

    event_type: str = "RetentionPolicyChangedEvent"
