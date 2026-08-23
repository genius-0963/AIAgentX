"""Outbox repository protocol."""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from app.domain.entities.outbox import OutboxEvent


class OutboxRepository(Protocol):
    """Repository for outbox event operations."""

    async def create(self, event: OutboxEvent) -> OutboxEvent:
        """Create a new outbox event."""
        ...

    async def get(self, event_id: UUID) -> OutboxEvent | None:
        """Get outbox event by ID."""
        ...

    async def get_unprocessed(
        self,
        limit: int = 100,
        event_types: list[str] | None = None,
    ) -> list[OutboxEvent]:
        """Get unprocessed outbox events.

        Args:
            limit: Maximum number of events
            event_types: Optional filter by event types

        Returns:
            List of unprocessed events
        """
        ...

    async def mark_processed(self, event_id: UUID) -> bool:
        """Mark event as processed."""
        ...

    async def mark_failed(self, event_id: UUID, error: str) -> bool:
        """Mark event as failed."""
        ...

    async def delete_processed(self, before: datetime) -> int:
        """Delete processed events older than timestamp.

        Returns:
            Number of events deleted
        """
        ...


from datetime import datetime