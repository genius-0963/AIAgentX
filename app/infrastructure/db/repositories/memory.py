"""Memory SQLAlchemy repository implementations."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import delete, select, func, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.memory import (
    MemoryRecord,
    MemoryRetentionPolicy,
    MemoryScope,
    SessionSummary,
)
from app.domain.repositories.memory import (
    MemoryRepository,
    MemoryRetentionPolicyRepository,
    SessionSummaryRepository,
)
from app.infrastructure.db.models.memory import (
    MemoryRecordModel,
    MemoryRetentionPolicyModel,
    SessionSummaryModel,
)
from app.infrastructure.db.repositories.base import BaseRepository


class SQLMemoryRepository(BaseRepository[MemoryRecord, MemoryRecordModel], MemoryRepository):
    """SQLAlchemy implementation of MemoryRepository."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, MemoryRecordModel, MemoryRecord)

    def _to_entity(self, model: MemoryRecordModel) -> MemoryRecord:
        return model.to_entity()

    def _to_model(self, entity: MemoryRecord) -> MemoryRecordModel:
        return MemoryRecordModel.from_entity(entity)

    async def create(self, record: MemoryRecord) -> MemoryRecord:
        model = self._to_model(record)
        await self._add(model)
        return self._to_entity(model)

    async def get(self, record_id: UUID) -> MemoryRecord | None:
        model = await self._get_by_id(record_id)
        return self._to_entity(model) if model else None

    async def get_by_tenant_agent(
        self,
        tenant_id: UUID,
        agent_id: UUID,
        limit: int = 100,
        offset: int = 0,
    ) -> list[MemoryRecord]:
        stmt = (
            select(MemoryRecordModel)
            .where(
                MemoryRecordModel.tenant_id == tenant_id,
                MemoryRecordModel.agent_id == agent_id,
            )
            .order_by(MemoryRecordModel.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return [self._to_entity(m) for m in result.scalars().all()]

    async def search_by_vector(
        self,
        tenant_id: UUID,
        agent_id: UUID,
        query_embedding: list[float],
        namespace: str,
        scope: MemoryScope,
        limit: int = 8,
        session_id: str | None = None,
    ) -> list[tuple[MemoryRecord, float]]:
        # Build the base query with tenant and agent filtering
        where_conditions = [
            MemoryRecordModel.tenant_id == tenant_id,
            MemoryRecordModel.agent_id == agent_id,
            MemoryRecordModel.namespace == namespace,
            MemoryRecordModel.scope == scope.value,
            MemoryRecordModel.embedding.isnot(None),
            # Exclude expired records
            (MemoryRecordModel.expires_at.is_(None)) | (MemoryRecordModel.expires_at > func.now()),
        ]

        if session_id:
            where_conditions.append(MemoryRecordModel.session_id == session_id)

        # Use cosine similarity for vector search with pgvector
        # The <=> operator returns cosine distance, so similarity = 1 - distance
        embedding_str = f"[{','.join(map(str, query_embedding))}]"
        similarity_expr = 1 - (MemoryRecordModel.embedding.op("<=>", is_comparison=True)(text(embedding_str)))

        stmt = (
            select(MemoryRecordModel, similarity_expr.label("similarity"))
            .where(*where_conditions)
            .order_by(similarity_expr.desc())
            .limit(limit)
        )

        result = await self._session.execute(stmt)
        rows = result.all()

        return [(self._to_entity(row[0]), float(row[1])) for row in rows]

    async def search_by_metadata(
        self,
        tenant_id: UUID,
        agent_id: UUID,
        namespace: str,
        scope: MemoryScope,
        metadata_filters: dict[str, object],
        limit: int = 100,
    ) -> list[MemoryRecord]:
        stmt = select(MemoryRecordModel).where(
            MemoryRecordModel.tenant_id == tenant_id,
            MemoryRecordModel.agent_id == agent_id,
            MemoryRecordModel.namespace == namespace,
            MemoryRecordModel.scope == scope.value,
        )

        # Add metadata filters using JSONB operators
        for key, value in metadata_filters.items():
            stmt = stmt.where(MemoryRecordModel.metadata[key].astext == str(value))

        stmt = stmt.limit(limit)
        result = await self._session.execute(stmt)
        return [self._to_entity(m) for m in result.scalars().all()]

    async def update(self, record: MemoryRecord) -> MemoryRecord:
        model = await self._get_by_id(record.id)
        if not model:
            raise ValueError(f"Memory record {record.id} not found")

        model.content_ciphertext = record.content_ciphertext
        model.embedding = record.embedding
        model.metadata = record.metadata
        model.allowed_use_label = record.allowed_use_label.value
        model.session_id = record.session_id
        model.expires_at = record.expires_at
        model.updated_at = record.updated_at

        await self._update(model)
        return self._to_entity(model)

    async def delete(self, record_id: UUID) -> bool:
        model = await self._get_by_id(record_id)
        if not model:
            return False
        await self._delete(model)
        return True

    async def delete_expired(self, tenant_id: UUID) -> int:
        stmt = delete(MemoryRecordModel).where(
            MemoryRecordModel.tenant_id == tenant_id,
            MemoryRecordModel.expires_at < func.now(),
        )
        result = await self._session.execute(stmt)
        await self._session.flush()
        return result.rowcount

    async def count_by_tenant(
        self,
        tenant_id: UUID,
        scope: MemoryScope | None = None,
    ) -> int:
        stmt = select(func.count()).select_from(MemoryRecordModel).where(
            MemoryRecordModel.tenant_id == tenant_id
        )
        if scope:
            stmt = stmt.where(MemoryRecordModel.scope == scope.value)
        result = await self._session.execute(stmt)
        return result.scalar() or 0

    async def get_storage_size_bytes(self, tenant_id: UUID) -> int:
        # Estimate storage size based on content length and metadata
        stmt = select(
            func.sum(func.length(MemoryRecordModel.content_ciphertext) + func.length(MemoryRecordModel.metadata::text))
        ).select_from(MemoryRecordModel).where(MemoryRecordModel.tenant_id == tenant_id)
        result = await self._session.execute(stmt)
        return result.scalar() or 0


class SQLSessionSummaryRepository(
    BaseRepository[SessionSummary, SessionSummaryModel], SessionSummaryRepository
):
    """SQLAlchemy implementation of SessionSummaryRepository."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, SessionSummaryModel, SessionSummary)

    def _to_entity(self, model: SessionSummaryModel) -> SessionSummary:
        return model.to_entity()

    def _to_model(self, entity: SessionSummary) -> SessionSummaryModel:
        return SessionSummaryModel.from_entity(entity)

    async def create(self, summary: SessionSummary) -> SessionSummary:
        model = self._to_model(summary)
        await self._add(model)
        return self._to_entity(model)

    async def get(self, summary_id: UUID) -> SessionSummary | None:
        model = await self._get_by_id(summary_id)
        return self._to_entity(model) if model else None

    async def get_by_session_id(
        self,
        tenant_id: UUID,
        agent_id: UUID,
        session_id: str,
    ) -> SessionSummary | None:
        stmt = select(SessionSummaryModel).where(
            SessionSummaryModel.tenant_id == tenant_id,
            SessionSummaryModel.agent_id == agent_id,
            SessionSummaryModel.session_id == session_id,
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def update(self, summary: SessionSummary) -> SessionSummary:
        model = await self._get_by_id(summary.id)
        if not model:
            raise ValueError(f"Session summary {summary.id} not found")

        model.summary_ciphertext = summary.summary_ciphertext
        model.metadata = summary.metadata
        model.updated_at = summary.updated_at

        await self._update(model)
        return self._to_entity(model)

    async def delete(self, summary_id: UUID) -> bool:
        model = await self._get_by_id(summary_id)
        if not model:
            return False
        await self._delete(model)
        return True

    async def delete_by_session_id(
        self,
        tenant_id: UUID,
        agent_id: UUID,
        session_id: str,
    ) -> bool:
        stmt = delete(SessionSummaryModel).where(
            SessionSummaryModel.tenant_id == tenant_id,
            SessionSummaryModel.agent_id == agent_id,
            SessionSummaryModel.session_id == session_id,
        )
        result = await self._session.execute(stmt)
        await self._session.flush()
        return result.rowcount > 0

    async def list_by_agent(
        self,
        tenant_id: UUID,
        agent_id: UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> list[SessionSummary]:
        stmt = (
            select(SessionSummaryModel)
            .where(
                SessionSummaryModel.tenant_id == tenant_id,
                SessionSummaryModel.agent_id == agent_id,
            )
            .order_by(SessionSummaryModel.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return [self._to_entity(m) for m in result.scalars().all()]


class SQLMemoryRetentionPolicyRepository(
    BaseRepository[MemoryRetentionPolicy, MemoryRetentionPolicyModel], MemoryRetentionPolicyRepository
):
    """SQLAlchemy implementation of MemoryRetentionPolicyRepository."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, MemoryRetentionPolicyModel, MemoryRetentionPolicy)

    def _to_entity(self, model: MemoryRetentionPolicyModel) -> MemoryRetentionPolicy:
        return model.to_entity()

    def _to_model(self, entity: MemoryRetentionPolicy) -> MemoryRetentionPolicyModel:
        return MemoryRetentionPolicyModel.from_entity(entity)

    async def create(self, policy: MemoryRetentionPolicy) -> MemoryRetentionPolicy:
        model = self._to_model(policy)
        await self._add(model)
        return self._to_entity(model)

    async def get(self, policy_id: UUID) -> MemoryRetentionPolicy | None:
        model = await self._get_by_id(policy_id)
        return self._to_entity(model) if model else None

    async def get_by_tenant_scope(
        self,
        tenant_id: UUID,
        scope: MemoryScope,
    ) -> MemoryRetentionPolicy | None:
        stmt = select(MemoryRetentionPolicyModel).where(
            MemoryRetentionPolicyModel.tenant_id == tenant_id,
            MemoryRetentionPolicyModel.scope == scope.value,
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def update(self, policy: MemoryRetentionPolicy) -> MemoryRetentionPolicy:
        model = await self._get_by_id(policy.id)
        if not model:
            raise ValueError(f"Retention policy {policy.id} not found")

        model.retention_days = policy.retention_days
        model.max_records_per_tenant = policy.max_records_per_tenant
        model.max_storage_mb = policy.max_storage_mb
        model.updated_at = policy.updated_at

        await self._update(model)
        return self._to_entity(model)

    async def delete(self, policy_id: UUID) -> bool:
        model = await self._get_by_id(policy_id)
        if not model:
            return False
        await self._delete(model)
        return True

    async def list_by_tenant(
        self,
        tenant_id: UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> list[MemoryRetentionPolicy]:
        stmt = (
            select(MemoryRetentionPolicyModel)
            .where(MemoryRetentionPolicyModel.tenant_id == tenant_id)
            .offset(offset)
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return [self._to_entity(m) for m in result.scalars().all()]

    async def upsert(self, policy: MemoryRetentionPolicy) -> MemoryRetentionPolicy:
        existing = await self.get_by_tenant_scope(policy.tenant_id, policy.scope)
        if existing:
            policy.id = existing.id
            return await self.update(policy)
        return await self.create(policy)
