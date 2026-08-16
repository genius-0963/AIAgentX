"""Base repository with common operations."""

from __future__ import annotations

from typing import Generic, TypeVar
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

T = TypeVar("T")
M = TypeVar("M")


class BaseRepository(Generic[T, M]):
    """Base repository with common CRUD operations."""

    def __init__(self, session: AsyncSession, model_class: type[M], entity_class: type[T]) -> None:
        self._session = session
        self._model_class = model_class
        self._entity_class = entity_class

    async def _get_by_id(self, id: UUID) -> M | None:
        """Get model by ID."""
        stmt = select(self._model_class).where(self._model_class.id == id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def _add(self, model: M) -> M:
        """Add model to session."""
        self._session.add(model)
        await self._session.flush()
        return model

    async def _update(self, model: M) -> M:
        """Update model in session."""
        await self._session.flush()
        return model

    async def _delete(self, model: M) -> None:
        """Delete model from session."""
        await self._session.delete(model)
        await self._session.flush()

    def _to_entity(self, model: M) -> T:
        """Convert model to domain entity. Override in subclasses."""
        raise NotImplementedError

    def _to_model(self, entity: T) -> M:
        """Convert domain entity to model. Override in subclasses."""
        raise NotImplementedError
