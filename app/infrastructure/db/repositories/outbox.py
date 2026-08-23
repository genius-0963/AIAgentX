"""Outbox SQLAlchemy repository implementation."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import select, delete, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.outbox import OutboxEvent
from app.domain.repositories.outbox import OutboxRepository
from app.infrastructure.db.models.outbox import OutboxEventModel
from app.infrastructure.db.repositories.base import BaseRepository

if TYPE_CHECKING:
    from app.domain.entities.outbox import OutboxEvent


class SQLOutboxRepository(BaseRepository[OutboxEvent, OutboxEventModel], OutboxRepository):
    """SQLAlchemy implementation of OutboxRepository."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, OutboxEventModel, OutboxEvent)

    def _to_entity(self, model: OutboxEventModel) -> OutboxEvent:
        return model.to_entity()

    def _to_model(self, entity: OutboxEvent) -> OutboxEventModel:
        return OutboxEventModel.from_entity(entity)

    async def create(self, event: OutboxEvent) -> OutboxEvent:
        model = self._to_model(event)
        await self._add(model)
        return self._to_entity(model)

    async def get(self, event_id: UUID) -> OutboxEvent | None:
        model = await self._get_by_id(event_id)
        return self._to_entity(model) if model else None

    async def get_unprocessed(
        self,
        limit: int = 100,
        event_types: list[str] | None = None,
    ) -> list[OutboxEvent]:
        stmt = select(OutboxEventModel).where(OutboxEventModel.processed_at.is_(None))

        if event_types:
            stmt = stmt.where(OutboxEventModel.event_type.in_(event_types))

        stmt = stmt.order_by(OutboxEventModel.created_at).limit(limit)

        result = await self._session.execute(stmt)
        return [self._to_entity(m) for m in result.scalars().all()]

    async def mark_processed(self, event_id: UUID) -> bool:
        stmt = (
            update(OutboxEventModel)
            .where(OutboxEventModel.id == event_id)
            .values(processed_at=datetime.utcnow(), updated_at=datetime.utcnow())
        )
        result = await self._session.execute(stmt)
        await self._session.flush()
        return result.rowcount > 0

    async def mark_failed(self, event_id: UUID, error: str) -> bool:
        stmt = (
            update(OutboxEventModel)
            .where(OutboxEventModel.id == event_id)
            .values(
                retry_count=OutboxEventModel.retry_count + 1,
                last_error=error,
                updated_at=datetime.utcnow(),
            )
        )
        result = await self._session.execute(stmt)
        await self._session.flush()
        return result.rowcount > 0

    async def delete_processed(self, before: datetime) -> int:
        stmt = delete(OutboxEventModel).where(
            OutboxEventModel.processed_at.is_not(None),
            OutboxEventModel.processed_at < before,
        )
        result = await self._session.execute(stmt)
        await self._session.flush()
        return result.rowcount