"""Integration tests for memory database operations."""

from __future__ import annotations

import pytest
from uuid import uuid4

from app.domain.entities.memory import (
    MemoryRecord,
    MemoryScope,
    AllowedUseLabel,
    SessionSummary,
    MemoryRetentionPolicy,
)
from app.infrastructure.db.repositories.memory import (
    SQLMemoryRepository,
    SQLSessionSummaryRepository,
    SQLMemoryRetentionPolicyRepository,
)


pytestmark = pytest.mark.integration


class TestMemoryRepositoryIntegration:
    """Integration tests for SQLMemoryRepository."""

    @pytest.fixture
    async def repo(self, db_session):
        return SQLMemoryRepository(db_session)

    @pytest.fixture
    def tenant_id(self):
        return uuid4()

    @pytest.fixture
    def agent_id(self):
        return uuid4()

    @pytest.mark.asyncio
    async def test_create_and_get_memory_record(self, repo, tenant_id, agent_id):
        record = MemoryRecord(
            id=uuid4(),
            tenant_id=tenant_id,
            agent_id=agent_id,
            scope=MemoryScope.DURABLE,
            namespace="test",
            content_ciphertext="encrypted_content",
            embedding=[0.1] * 1536,
            metadata={"key": "value"},
            allowed_use_label=AllowedUseLabel.PUBLIC,
        )

        created = await repo.create(record)
        assert created.id == record.id

        retrieved = await repo.get(created.id)
        assert retrieved is not None
        assert retrieved.id == record.id
        assert retrieved.tenant_id == tenant_id
        assert retrieved.agent_id == agent_id
        assert retrieved.namespace == "test"
        assert retrieved.content_ciphertext == "encrypted_content"

    @pytest.mark.asyncio
    async def test_get_nonexistent_record(self, repo):
        result = await repo.get(uuid4())
        assert result is None

    @pytest.mark.asyncio
    async def test_get_by_tenant_agent(self, repo, tenant_id, agent_id):
        records = [
            MemoryRecord(
                id=uuid4(),
                tenant_id=tenant_id,
                agent_id=agent_id,
                scope=MemoryScope.DURABLE,
                namespace="test",
                content_ciphertext=f"content_{i}",
                metadata={"index": i},
                allowed_use_label=AllowedUseLabel.PUBLIC,
            )
            for i in range(5)
        ]

        for r in records:
            await repo.create(r)

        results = await repo.get_by_tenant_agent(tenant_id, agent_id, limit=10)
        assert len(results) == 5

    @pytest.mark.asyncio
    async def test_search_by_vector(self, repo, tenant_id, agent_id):
        # Create records with embeddings
        records = [
            MemoryRecord(
                id=uuid4(),
                tenant_id=tenant_id,
                agent_id=agent_id,
                scope=MemoryScope.DURABLE,
                namespace="test",
                content_ciphertext=f"content_{i}",
                embedding=[float(i)] * 1536,
                metadata={},
                allowed_use_label=AllowedUseLabel.PUBLIC,
            )
            for i in range(10)
        ]

        for r in records:
            await repo.create(r)

        # Search with query embedding similar to record 5
        query_embedding = [5.0] * 1536
        results = await repo.search_by_vector(
            tenant_id=tenant_id,
            agent_id=agent_id,
            query_embedding=query_embedding,
            namespace="test",
            scope=MemoryScope.DURABLE,
            limit=3,
        )

        assert len(results) <= 3
        # First result should be most similar to record 5
        assert results[0][0].metadata == {}


class TestSessionSummaryRepositoryIntegration:
    """Integration tests for SQLSessionSummaryRepository."""

    @pytest.fixture
    async def repo(self, db_session):
        return SQLSessionSummaryRepository(db_session)

    @pytest.fixture
    def tenant_id(self):
        return uuid4()

    @pytest.fixture
    def agent_id(self):
        return uuid4()

    @pytest.mark.asyncio
    async def test_create_and_get_session_summary(self, repo, tenant_id, agent_id):
        summary = SessionSummary(
            id=uuid4(),
            tenant_id=tenant_id,
            agent_id=agent_id,
            session_id="test-session",
            summary_ciphertext="encrypted_summary",
            metadata={"message_count": 10},
        )

        created = await repo.create(summary)
        assert created.session_id == "test-session"

        retrieved = await repo.get_by_session_id(tenant_id, agent_id, "test-session")
        assert retrieved is not None
        assert retrieved.session_id == "test-session"
        assert retrieved.metadata["message_count"] == 10

    @pytest.mark.asyncio
    async def test_list_by_agent(self, repo, tenant_id, agent_id):
        summaries = [
            SessionSummary(
                id=uuid4(),
                tenant_id=tenant_id,
                agent_id=agent_id,
                session_id=f"session-{i}",
                summary_ciphertext=f"summary_{i}",
                metadata={"message_count": i},
            )
            for i in range(3)
        ]

        for s in summaries:
            await repo.create(s)

        results = await repo.list_by_agent(tenant_id, agent_id, limit=10)
        assert len(results) == 3


class TestRetentionPolicyRepositoryIntegration:
    """Integration tests for SQLMemoryRetentionPolicyRepository."""

    @pytest.fixture
    async def repo(self, db_session):
        return SQLMemoryRetentionPolicyRepository(db_session)

    @pytest.fixture
    def tenant_id(self):
        return uuid4()

    @pytest.mark.asyncio
    async def test_upsert_policy(self, repo, tenant_id):
        policy = MemoryRetentionPolicy(
            id=uuid4(),
            tenant_id=tenant_id,
            scope=MemoryScope.DURABLE,
            retention_days=30,
            max_records_per_tenant=1000,
            max_storage_mb=100,
        )

        created = await repo.upsert(policy)
        assert created.retention_days == 30

        # Update the policy
        policy.retention_days = 60
        updated = await repo.upsert(policy)
        assert updated.retention_days == 60
        assert updated.id == created.id  # Same ID

    @pytest.mark.asyncio
    async def test_get_by_tenant_scope(self, repo, tenant_id):
        policy = MemoryRetentionPolicy(
            id=uuid4(),
            tenant_id=tenant_id,
            scope=MemoryScope.DURABLE,
            retention_days=30,
        )

        await repo.create(policy)

        retrieved = await repo.get_by_tenant_scope(tenant_id, MemoryScope.DURABLE)
        assert retrieved is not None
        assert retrieved.retention_days == 30