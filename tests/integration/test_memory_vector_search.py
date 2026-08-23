"""Integration tests for vector search accuracy."""

from __future__ import annotations

import pytest
from uuid import uuid4

from app.domain.entities.memory import (
    MemoryRecord,
    MemoryScope,
    AllowedUseLabel,
)
from app.infrastructure.db.repositories.memory import SQLMemoryRepository


pytestmark = pytest.mark.integration


class TestVectorSearchAccuracy:
    """Integration tests for pgvector similarity search."""

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
    async def test_vector_search_returns_similar_results(self, repo, tenant_id, agent_id):
        """Test that similar embeddings return high similarity scores."""
        # Create records with known embeddings
        # Record 1: embedding all 1.0
        # Record 2: embedding all -1.0
        # Record 3: embedding all 0.5
        
        records = [
            MemoryRecord(
                id=uuid4(),
                tenant_id=tenant_id,
                agent_id=agent_id,
                scope=MemoryScope.DURABLE,
                namespace="test",
                content_ciphertext="content_1",
                embedding=[1.0] * 1536,
                metadata={"label": "positive"},
                allowed_use_label=AllowedUseLabel.PUBLIC,
            ),
            MemoryRecord(
                id=uuid4(),
                tenant_id=tenant_id,
                agent_id=agent_id,
                scope=MemoryScope.DURABLE,
                namespace="test",
                content_ciphertext="content_2",
                embedding=[-1.0] * 1536,
                metadata={"label": "negative"},
                allowed_use_label=AllowedUseLabel.PUBLIC,
            ),
            MemoryRecord(
                id=uuid4(),
                tenant_id=tenant_id,
                agent_id=agent_id,
                scope=MemoryScope.DURABLE,
                namespace="test",
                content_ciphertext="content_3",
                embedding=[0.5] * 1536,
                metadata={"label": "neutral"},
                allowed_use_label=AllowedUseLabel.PUBLIC,
            ),
        ]

        for r in records:
            await repo.create(r)

        # Query with embedding close to record 1 (all 1.0)
        query_embedding = [0.9] * 1536
        results = await repo.search_by_vector(
            tenant_id=tenant_id,
            agent_id=agent_id,
            query_embedding=query_embedding,
            namespace="test",
            scope=MemoryScope.DURABLE,
            limit=3,
        )

        assert len(results) == 3
        # First result should be record 1 (highest similarity)
        assert results[0][0].metadata["label"] == "positive"
        assert results[0][1] > 0.9  # High similarity

        # Second should be record 3
        assert results[1][0].metadata["label"] == "neutral"
        assert results[1][1] > 0.5

        # Third should be record 2 (lowest similarity)
        assert results[2][0].metadata["label"] == "negative"
        assert results[2][1] < 0.0  # Negative similarity

    @pytest.mark.asyncio
    async def test_vector_search_filters_by_namespace(self, repo, tenant_id, agent_id):
        """Test that search filters by namespace."""
        # Create records in different namespaces
        ns1_record = MemoryRecord(
            id=uuid4(),
            tenant_id=tenant_id,
            agent_id=agent_id,
            scope=MemoryScope.DURABLE,
            namespace="namespace1",
            content_ciphertext="content_ns1",
            embedding=[1.0] * 1536,
            metadata={},
            allowed_use_label=AllowedUseLabel.PUBLIC,
        )
        ns2_record = MemoryRecord(
            id=uuid4(),
            tenant_id=tenant_id,
            agent_id=agent_id,
            scope=MemoryScope.DURABLE,
            namespace="namespace2",
            content_ciphertext="content_ns2",
            embedding=[1.0] * 1536,
            metadata={},
            allowed_use_label=AllowedUseLabel.PUBLIC,
        )

        await repo.create(ns1_record)
        await repo.create(ns2_record)

        # Search only namespace1
        query_embedding = [1.0] * 1536
        results = await repo.search_by_vector(
            tenant_id=tenant_id,
            agent_id=agent_id,
            query_embedding=query_embedding,
            namespace="namespace1",
            scope=MemoryScope.DURABLE,
            limit=10,
        )

        assert len(results) == 1
        assert results[0][0].namespace == "namespace1"

    @pytest.mark.asyncio
    async def test_vector_search_filters_by_scope(self, repo, tenant_id, agent_id):
        """Test that search filters by scope."""
        durable_record = MemoryRecord(
            id=uuid4(),
            tenant_id=tenant_id,
            agent_id=agent_id,
            scope=MemoryScope.DURABLE,
            namespace="test",
            content_ciphertext="durable_content",
            embedding=[1.0] * 1536,
            metadata={},
            allowed_use_label=AllowedUseLabel.PUBLIC,
        )
        session_record = MemoryRecord(
            id=uuid4(),
            tenant_id=tenant_id,
            agent_id=agent_id,
            scope=MemoryScope.SESSION,
            namespace="test",
            content_ciphertext="session_content",
            embedding=[1.0] * 1536,
            metadata={},
            allowed_use_label=AllowedUseLabel.PUBLIC,
        )

        await repo.create(durable_record)
        await repo.create(session_record)

        query_embedding = [1.0] * 1536

        # Search DURABLE only
        durable_results = await repo.search_by_vector(
            tenant_id=tenant_id,
            agent_id=agent_id,
            query_embedding=query_embedding,
            namespace="test",
            scope=MemoryScope.DURABLE,
            limit=10,
        )

        assert len(durable_results) == 1
        assert durable_results[0][0].scope == MemoryScope.DURABLE

        # Search SESSION only
        session_results = await repo.search_by_vector(
            tenant_id=tenant_id,
            agent_id=agent_id,
            query_embedding=query_embedding,
            namespace="test",
            scope=MemoryScope.SESSION,
            limit=10,
        )

        assert len(session_results) == 1
        assert session_results[0][0].scope == MemoryScope.SESSION

    @pytest.mark.asyncio
    async def test_vector_search_filters_expired(self, repo, tenant_id, agent_id):
        """Test that search excludes expired records."""
        from datetime import UTC, datetime, timedelta

        active_record = MemoryRecord(
            id=uuid4(),
            tenant_id=tenant_id,
            agent_id=agent_id,
            scope=MemoryScope.DURABLE,
            namespace="test",
            content_ciphertext="active_content",
            embedding=[1.0] * 1536,
            metadata={},
            allowed_use_label=AllowedUseLabel.PUBLIC,
            expires_at=datetime.now(UTC) + timedelta(days=1),
        )
        expired_record = MemoryRecord(
            id=uuid4(),
            tenant_id=tenant_id,
            agent_id=agent_id,
            scope=MemoryScope.DURABLE,
            namespace="test",
            content_ciphertext="expired_content",
            embedding=[1.0] * 1536,
            metadata={},
            allowed_use_label=AllowedUseLabel.PUBLIC,
            expires_at=datetime.now(UTC) - timedelta(days=1),
        )

        await repo.create(active_record)
        await repo.create(expired_record)

        query_embedding = [1.0] * 1536
        results = await repo.search_by_vector(
            tenant_id=tenant_id,
            agent_id=agent_id,
            query_embedding=query_embedding,
            namespace="test",
            scope=MemoryScope.DURABLE,
            limit=10,
        )

        assert len(results) == 1
        assert results[0][0].id == active_record.id

    @pytest.mark.asyncio
    async def test_vector_search_session_filter(self, repo, tenant_id, agent_id):
        """Test that search filters by session_id."""
        session1_record = MemoryRecord(
            id=uuid4(),
            tenant_id=tenant_id,
            agent_id=agent_id,
            scope=MemoryScope.SESSION,
            namespace="test",
            content_ciphertext="session1_content",
            embedding=[1.0] * 1536,
            metadata={},
            allowed_use_label=AllowedUseLabel.PUBLIC,
            session_id="session-1",
        )
        session2_record = MemoryRecord(
            id=uuid4(),
            tenant_id=tenant_id,
            agent_id=agent_id,
            scope=MemoryScope.SESSION,
            namespace="test",
            content_ciphertext="session2_content",
            embedding=[1.0] * 1536,
            metadata={},
            allowed_use_label=AllowedUseLabel.PUBLIC,
            session_id="session-2",
        )

        await repo.create(session1_record)
        await repo.create(session2_record)

        query_embedding = [1.0] * 1536
        results = await repo.search_by_vector(
            tenant_id=tenant_id,
            agent_id=agent_id,
            query_embedding=query_embedding,
            namespace="test",
            scope=MemoryScope.SESSION,
            limit=10,
            session_id="session-1",
        )

        assert len(results) == 1
        assert results[0][0].session_id == "session-1"