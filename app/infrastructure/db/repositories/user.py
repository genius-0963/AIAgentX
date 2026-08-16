"""User SQLAlchemy repository."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.user import User
from app.domain.repositories.user import UserRepository
from app.infrastructure.db.models.user import UserModel
from app.infrastructure.db.repositories.base import BaseRepository


class SQLUserRepository(BaseRepository[User, UserModel], UserRepository):
    """SQLAlchemy implementation of UserRepository."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, UserModel, User)

    def _to_entity(self, model: UserModel) -> User:
        return User(
            id=model.id,
            tenant_id=model.tenant_id,
            email=model.email,
            password_hash=model.password_hash,
            status=model.status,
            last_login_at=model.last_login_at,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    def _to_model(self, entity: User) -> UserModel:
        return UserModel(
            id=entity.id,
            tenant_id=entity.tenant_id,
            email=entity.email,
            password_hash=entity.password_hash,
            status=entity.status,
            last_login_at=entity.last_login_at,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
        )

    async def create(self, user: User) -> User:
        model = self._to_model(user)
        await self._add(model)
        return self._to_entity(model)

    async def get(self, user_id: UUID) -> User | None:
        model = await self._get_by_id(user_id)
        return self._to_entity(model) if model else None

    async def get_by_email(self, tenant_id: UUID, email: str) -> User | None:
        stmt = select(UserModel).where(UserModel.tenant_id == tenant_id, UserModel.email == email)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def update(self, user: User) -> User:
        model = await self._get_by_id(user.id)
        if not model:
            raise ValueError(f"User {user.id} not found")
        model.email = user.email
        model.password_hash = user.password_hash
        model.status = user.status
        model.last_login_at = user.last_login_at
        model.updated_at = user.updated_at
        await self._update(model)
        return self._to_entity(model)

    async def list(
        self,
        tenant_id: UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> Sequence[User]:
        stmt = select(UserModel).where(UserModel.tenant_id == tenant_id).offset(offset).limit(limit)
        result = await self._session.execute(stmt)
        return [self._to_entity(m) for m in result.scalars().all()]

    async def delete(self, user_id: UUID) -> bool:
        model = await self._get_by_id(user_id)
        if not model:
            return False
        await self._delete(model)
        return True
