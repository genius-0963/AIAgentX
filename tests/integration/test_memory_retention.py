"""Integration tests for memory retention and cleanup."""

from __future__ import annotations

import pytest
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from app.domain.entities.memory import (
    MemoryRecord,
    MemoryScope,
    AllowedUseLabel,
    MemoryRetentionPolicy,
)
from app.infrastructure.db.repositories.memory import (
    SQLMemoryRepository,
    SQLMemoryRetentionPolicyRepository,
)
from app.application.services.memory_cleanup_service import MemoryCleanupService


pytestmark = pytest.mark.integration


class TestMemoryRetention:
    """Integration tests for retention policies and cleanup."""

    @pytest.fixture
    def tenant_id(self):
        return uuid4()

    @pytest.fixture
    def agent_id(self):
        return uuid4()

    @pytest.fixture
    async def memory_repo(self, db_session):
        return SQLMemoryRepository(db_session)

    @pytest.fixture
    async def retention_repo(self, db_session):
        return SQLMemoryRetentionPolicyRepository(db_session)

    @pytest.fixture
    async def cleanup_service(self, memory_repo, retention_repo):
        return MemoryCleanupService(memory_repo, retention_repo)

    @pytest.mark.asyncio
    async def test_retention_policy_creation(self, retention_repo, tenant_id):
        policy = MemoryRetentionPolicy(
            id=uuid4(),
            tenant_id=tenant_id,
            scope=MemoryScope.DURABLE,
            retention_days=30,
            max_records_per_tenant=1000,
            max_storage_mb=100,
        )

        created = await retention_repo.upsert(policy)
        assert created.retention_days == 30

        retrieved = await retention_repo.get_by_tenant_scope(tenant_id, MemoryScope.DURABLE)
        assert retrieved.retention_days == 30
        assert retrieved.max_records_per_tenant == 1000

    @pytest.mark.asyncio
    async def test_multiple_scope_policies(self, retention_repo, tenant_id):
        policies = [
            MemoryRetentionPolicy(
                id=uuid4(),
                tenant_id=tenant_id,
                scope=scope,
                retention_days=days,
            )
            for scope, days in [
                (MemoryScope.EPHEMERAL, 1),
                (MemoryScope.SESSION, 7),
                (MemoryScope.DURABLE, 90),
            ]
        ]

        for p in policies:
            await retention_repo.upsert(p)

        # Verify all three scopes have policies
        for scope in [MemoryScope.EPHEMERAL, MemoryScope.SESSION, MemoryScope.DURABLE]:
            retrieved = await retention_repo.get_by_tenant_scope(tenant_id, scope)
            assert retrieved is not None

    @pytest.mark.asyncio
    async def test_delete_expired_records(self, memory_repo, tenant_id, agent_id):
        # Create expired record
        expired_record = MemoryRecord(
            id=uuid4(),
            tenant_id=tenant_id,
            agent_id=agent_id,
            scope=MemoryScope.EPHEMERAL,
            namespace="test",
            content_ciphertext="expired_content",
            embedding=[1.0] * 1536,
            metadata={},
            allowed_use_label=AllowedUseLabel.PUBLIC,
            expires_at=datetime.now(UTC) - timedelta(days=1),
        )
        await memory_repo.create(expired_record)

        # Create active record
        active_record = MemoryRecord(
            id=uuid4(),
            tenant_id=tenant_id,
            agent_id=agent_id,
            scope=MemoryScope.EPHEMERAL,
            namespace="test",
            content_ciphertext="active_content",
            embedding=[1.0] * 1536,
            metadata={},
            allowed_use_label=AllowedUseLabel.PUBLIC,
            expires_at=datetime.now(UTC) + timedelta(days=1),
        )
        await memory_repo.create(active_record)

        # Delete expired
        deleted = await memory_repo.delete_expired(tenant_id)
        assert deleted == 1

        # Verify active record still exists
        results = await memory_repo.get_by_tenant_agent(tenant_id, agent_id)
        assert len(results) == 1
        assert results[0].id == active_record.id

    @pytest.mark.asyncio
    async def test_cleanup_service_expired_cleanup(self, cleanup_service, memory_repo, tenant_id, agent_id):
        # Create expired records across scopes
        for scope in [MemoryScope.EPHEMERAL, MemoryScope.SESSION, MemoryScope.DURABLE]:
            record = MemoryRecord(
                id=uuid4(),
                tenant_id=tenant_id,
                agent_id=agent_id,
                scope=scope,
                namespace="test",
                content_ciphertext="expired",
                embedding=[1.0] * 1536,
                metadata={},
                allowed_use_label=AllowedUseLabel.PUBLIC,
                expires_at=datetime.now(UTC) - timedelta(days=1),
            )
            await memory_repo.create(record)

        result = await cleanup_service.cleanup_expired(tenant_id)

        assert result.expired_deleted == 3
        assert result.storage_freed_mb > 0

    @pytest.mark.asyncio
    async def test_quota_enforcement(self, cleanup_service, memory_repo, retention_repo, tenant_id):
        # Set up quota policy
        policy = MemoryRetentionPolicy(
            id=uuid4(),
            tenant_id=tenant_id,
            scope=MemoryScope.DURABLE,
            retention_days=30,
            max_records_per_tenant=5,
            max_storage_mb=10,
        )
        await retention_repo.upsert(policy)

        # Add 5 records (at quota)
        for i in range(5):
            record = MemoryRecord(
                id=uuid4(),
                tenant_id=tenant_id,
                agent_id=uuid4(),
                scope=MemoryScope.DURABLE,
                namespace="test",
                content_ciphertext="content_" + "x" * 100000,  # ~100KB each
                embedding=[1.0] * 1536,
                metadata={},
                allowed_use_label=AllowedUseLabel.PUBLIC,
            )
            await memory_repo.create(record)

        # Check quota
        statuses = await cleanup_service.enforce_quotas(tenant_id)
        durable_status = next(s for s in statuses if s.scope == MemoryScope.DURABLE)

        assert durable_status.is_over_quota is True
        assert durable_status.max_records == 5
        assert durable_status.record_count == 5

    @pytest.mark.asyncio
    async def test_storage_quota_enforcement(self, cleanup_service, memory_repo, retention_repo, tenant_id):
        policy = MemoryRetentionPolicy(
            id=uuid4(),
            tenant_id=tenant_id,
            scope=MemoryScope.DURABLE,
            retention_days=30,
            max_storage_mb=1,  # 1MB limit
        )
        await retention_repo.upsert(policy)

        # Add record exceeding storage
        record = MemoryRecord(
            id=uuid4(),
            tenant_id=tenant_id,
            agent_id=uuid4(),
            scope=MemoryScope.DURABLE,
            namespace="test",
            content_ciphertext="x" * (2 * 1024 * 1024),  # 2MB
            embedding=[1.0] * 1536,
            metadata={},
            allowed_use_label=AllowedUseLabel.PUBLIC,
        )
        await memory_repo.create(record)

        statuses = await cleanup_service.enforce_quotas(tenant_id)
        durable_status = next(s for s in statuses if s.scope == MemoryScope.DURABLE)

        assert durable_status.is_over_quota is True
        assert "Storage" in durable_status.quota_exceeded_reason

    @pytest.mark.asyncio
    async def test_full_cleanup_run(self, cleanup_service, memory_repo, retention_repo, tenant_id, agent_id):
        # Set up policies
        for scope, days in [(MemoryScope.EPHEMERAL, 1), (MemoryScope.DURABLE, 30)]:
            policy = MemoryRetentionPolicy(
                id=uuid4(),
                tenant_id=tenant_id,
                scope=scope,
                retention_days=days,
            )
            await retention_repo.upsert(policy)

        # Add expired record
        expired = MemoryRecord(
            id=uuid4(),
            tenant_id=tenant_id,
            agent_id=agent_id,
            scope=MemoryScope.EPHEMERAL,
            namespace="test",
            content_ciphertext="expired",
            embedding=[1.0] * 1536,
            metadata={},
            allowed_use_label=AllowedUseLabel.PUBLIC,
            expires_at=datetime.now(UTC) - timedelta(days=1),
        )
        await memory_repo.create(expired)

        # Add active record
        active = MemoryRecord(
            id=uuid4(),
            tenant_id=tenant_id,
            agent_id=agent_id,
            scope=MemoryScope.DURABLE,
            namespace="test",
            content_ciphertext="active",
            embedding=[1.0] * 1536,
            metadata={},
            allowed_use_label=AllowedUseLabel.PUBLIC,
        )
        await memory_repo.create(active)

        result = await cleanup_service.run_full_cleanup(tenant_id)

        assert result["tenant_id"] == str(tenant_id)
        assert result["expired_cleanup"]["deleted"] >= 1
        assert len(result["retention_enforcement"]) == 3
        assert len(result["quota_status"]) == 3