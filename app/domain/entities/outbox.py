"""Outbox event domain entity."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from app.domain.entities.base import Entity


@dataclass(slots=True, kw_only=True)
class OutboxEvent(Entity):
    """Outbox event for reliable event publishing."""

    event_type: str
    aggregate_id: str
    aggregate_type: str
    payload: dict[str, Any] = field(default_factory=dict)
    processed_at: datetime | None = None
    retry_count: int = 0
    last_error: str | None = None

    @classmethod
    def create(
        cls,
        event_type: str,
        aggregate_id: str,
        aggregate_type: str,
        payload: dict[str, Any],
    ) -> "OutboxEvent":
        """Create a new outbox event."""
        return cls(
            id=uuid4(),
            event_type=event_type,
            aggregate_id=aggregate_id,
            aggregate_type=aggregate_type,
            payload=payload,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

    def mark_processed(self) -> None:
        """Mark event as processed."""
        self.processed_at = datetime.now(UTC)
        self.touch()

    def mark_failed(self, error: str) -> None:
        """Mark event as failed."""
        self.retry_count += 1
        self.last_error = error
        self.touch()