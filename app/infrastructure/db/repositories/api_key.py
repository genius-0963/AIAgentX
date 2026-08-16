"""API Key SQLAlchemy repository."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import func

from app.domain.entities.api_key import APIKey
from app.domain.repositories.api_key import APIKeyRepository
from app.infrastructure.db.models.api_key import APIKeyModel
from app.infrastructure.db.repositories.base import BaseRepository


class SQLAPIKeyRepository(BaseRepository[APIKey, APIKeyModel], APIKeyRepository):
    """SQLAlchemy implementation of APIKeyRepository."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, APIKeyModel, APIKey)

    def _to_entity(self, model: APIKeyModel) -> APIKey:
        return APIKey(
            id=model.id,
            tenant_id=model.tenant_id,
            key_hash=model.key_hash,
            name=model.name,
            scopes=model.scopes,
            expires_at=model.expires_at,
            revoked_at=model.revoked_at,
            last_used_at=model.last_used_at,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    def _to_model(self, entity: APIKey) -> APIKeyModel:
        return APIKeyModel(
            id=entity.id,
            tenant_id=entity.tenant_id,
            key_hash=entity.key_hash,
            name=entity.name,
            scopes=entity.scopes,
            expires_at=entity.expires_at,
            revoked_at=entity.revoked_at,
            last_used_at=entity.last_used_at,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
        )

    async def create(self, api_key: APIKey) -> APIKey:
        model = self._to_model(api_key)
        await self._add(model)
        return self._to_entity(model)

    async def get(self, key_id: UUID) -> APIKey | None:
        model = await self._get_by_id(key_id)
        return self._to_entity(model) if model else None

    async def get_by_hash(self, key_hash: str) -> APIKey | None:
        stmt = select(APIKeyModel).where(APIKeyModel.key_hash == key_hash)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def update(self, api_key: APIKey) -> APIKey:
        model = await self._get_by_id(api_key.id)
        if not model:
            raise ValueError(f"API Key {api_key.id} not found")
        model.name = api_key.name
        model.scopes = api_key.scopes
        model.expires_at = api_key.expires_at
        model.revoked_at = api_key.revoked_at
        model.last_used_at = api_key.last_used_at
        model.updated_at = api_key.updated_at
        await self._update(model)
        return self._to_entity(model)

    async def list(
        self,
        tenant_id: UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> Sequence[APIKey]:
        stmt = (
            select(APIKeyModel)
            .where(APIKeyModel.tenant_id == tenant_id)
            .offset(offset)
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return [self._to_entity(m) for m in result.scalars().all()]

    async def revoke(self, key_id: UUID) -> bool:
        model = await self._get_by_id(key_id)
        if not model:
            return False
        model.revoked_at = model.updated_at  # will be set to now by onupdate
        await self._update(model)
        return True

    async def cleanup_expired(self) -> int:
        stmt = delete(APIKeyModel).where(
            APIKeyModel.expires_at.is_not(None),
            APIKeyModel.expires_at < func.now(),
        )
        result = await self._session.execute(stmt)
        return result.rowcount
