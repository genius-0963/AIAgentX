"""Tenant SQLAlchemy repository."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.tenant import Tenant, TenantPlan, TenantStatus
from app.domain.repositories.tenant import TenantRepository
from app.infrastructure.db.models.tenant import TenantModel
from app.infrastructure.db.repositories.base import BaseRepository


class SQLTenantRepository(BaseRepository[Tenant, TenantModel], TenantRepository):
    """SQLAlchemy implementation of TenantRepository."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, TenantModel, Tenant)

    def _to_entity(self, model: TenantModel) -> Tenant:
        return Tenant(
            id=model.id,
            slug=model.slug,
            plan=model.plan,
            status=model.status,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    def _to_model(self, entity: Tenant) -> TenantModel:
        return TenantModel(
            id=entity.id,
            slug=entity.slug,
            plan=entity.plan,
            status=entity.status,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
        )

    async def create(self, tenant: Tenant) -> Tenant:
        model = self._to_model(tenant)
        await self._add(model)
        return self._to_entity(model)

    async def get(self, tenant_id: UUID) -> Tenant | None:
        model = await self._get_by_id(tenant_id)
        return self._to_entity(model) if model else None

    async def get_by_slug(self, slug: str) -> Tenant | None:
        stmt = select(TenantModel).where(TenantModel.slug == slug)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def update(self, tenant: Tenant) -> Tenant:
        model = await self._get_by_id(tenant.id)
        if not model:
            raise ValueError(f"Tenant {tenant.id} not found")
        model.slug = tenant.slug
        model.plan = tenant.plan
        model.status = tenant.status
        model.updated_at = tenant.updated_at
        await self._update(model)
        return self._to_entity(model)

    async def list(
        self,
        status: TenantStatus | None = None,
        plan: TenantPlan | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Sequence[Tenant]:
        stmt = select(TenantModel).offset(offset).limit(limit)
        if status:
            stmt = stmt.where(TenantModel.status == status)
        if plan:
            stmt = stmt.where(TenantModel.plan == plan)
        result = await self._session.execute(stmt)
        return [self._to_entity(m) for m in result.scalars().all()]

    async def delete(self, tenant_id: UUID) -> bool:
        model = await self._get_by_id(tenant_id)
        if not model:
            return False
        model.status = TenantStatus.DELETED
        await self._update(model)
        return True
