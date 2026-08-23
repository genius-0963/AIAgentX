"""Outbox event model for reliable event publishing."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import Base, TimestampMixin, UUIDMixin


class OutboxEventModel(Base, UUIDMixin, TimestampMixin):
    """Outbox event database model for reliable event publishing."""

    __tablename__ = "outbox_events"

    event_type: Mapped[str] = mapped_column(Text(), nullable=False, index=True)
    aggregate_id: Mapped[str] = mapped_column(Text(), nullable=False, index=True)
    aggregate_type: Mapped[str] = mapped_column(Text(), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB(astext_type=Text()), nullable=False, default=dict)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    retry_count: Mapped[int] = mapped_column(default=0)
    last_error: Mapped[str | None] = mapped_column(Text(), nullable=True)

    __table_args__ = (
        Index("ix_outbox_events_unprocessed", "processed_at", postgresql_where=Text("processed_at IS NULL")),
        Index("ix_outbox_events_aggregate", "aggregate_type", "aggregate_id"),
    )

    def to_entity(self) -> "OutboxEvent":
        """Convert to domain entity."""
        from app.domain.entities.outbox import OutboxEvent
        return OutboxEvent(
            id=self.id,
            event_type=self.event_type,
            aggregate_id=self.aggregate_id,
            aggregate_type=self.aggregate_type,
            payload=self.payload,
            processed_at=self.processed_at,
            retry_count=self.retry_count,
            last_error=self.last_error,
            created_at=self.created_at,
            updated_at=self.updated_at,
        )

    @classmethod
    def from_entity(cls, event: "OutboxEvent") -> "OutboxEventModel":
        """Create from domain entity."""
        return cls(
            id=event.id,
            event_type=event.event_type,
            aggregate_id=event.aggregate_id,
            aggregate_type=event.aggregate_type,
            payload=event.payload,
            processed_at=event.processed_at,
            retry_count=event.retry_count,
            last_error=event.last_error,
            created_at=event.created_at,
            updated_at=event.updated_at,
        )