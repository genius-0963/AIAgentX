"""Unit tests for memory cleanup service."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from app.domain.entities.memory import MemoryScope, MemoryRetentionPolicy
from app.domain.repositories.memory import MemoryRepository, MemoryRetentionPolicyRepository
from app.application.services.memory_cleanup_service import MemoryCleanupService, CleanupResult, QuotaStatus


class TestMemoryCleanupService:
    """Tests for MemoryCleanupService."""

    def setup_method(self) -> None:
        self.tenant_id = uuid4()

        self.memory_repo = AsyncMock(spec=MemoryRepository)
        self.retention_repo = AsyncMock(spec=MemoryRetentionPolicyRepository)

        self.service = MemoryCleanupService(
            memory_repository=self.memory_repo,
            retention_policy_repository=self.retention_repo,
        )

    @pytest.mark.asyncio
    async def test_cleanup_expired(self) -> None:
        self.memory_repo.delete_expired.return_value = 5
        self.memory_repo.get_storage_size_bytes.side_effect = [1000000, 500000]  # Before, after

        result = await self.service.cleanup_expired(self.tenant_id)

        assert isinstance(result, CleanupResult)
        assert result.tenant_id == self.tenant_id
        assert result.expired_deleted == 5
        assert result.storage_freed_mb == pytest.approx(0.476, rel=0.1)

    @pytest.mark.asyncio
    async def test_enforce_retention_policies(self) -> None:
        policy = MemoryRetentionPolicy(
            id=uuid4(),
            tenant_id=self.tenant_id,
            scope=MemoryScope.DURABLE,
            retention_days=30,
        )
        self.retention_repo.get_by_tenant_scope.return_value = policy
        self.memory_repo.get_storage_size_bytes.side_effect = [1000000, 500000]
        self.memory_repo.delete_expired.return_value = 3

        results = await self.service.enforce_retention_policies(self.tenant_id)

        assert len(results) == 3  # EPHEMERAL, SESSION, DURABLE
        assert all(isinstance(r, CleanupResult) for r in results)

    @pytest.mark.asyncio
    async def test_check_scope_quota_no_policy(self) -> None:
        self.retention_repo.get_by_tenant_scope.return_value = None
        self.memory_repo.count_by_tenant.return_value = 100
        self.memory_repo.get_storage_size_bytes.return_value = 50 * 1024 * 1024

        status = await self.service._check_scope_quota(self.tenant_id, MemoryScope.DURABLE)

        assert isinstance(status, QuotaStatus)
        assert status.is_over_quota is False
        assert status.max_records is None
        assert status.max_storage_mb is None

    @pytest.mark.asyncio
    async def test_check_scope_quota_exceeded_records(self) -> None:
        policy = MemoryRetentionPolicy(
            id=uuid4(),
            tenant_id=self.tenant_id,
            scope=MemoryScope.DURABLE,
            retention_days=30,
            max_records_per_tenant=100,
        )
        self.retention_repo.get_by_tenant_scope.return_value = policy
        self.memory_repo.count_by_tenant.return_value = 100
        self.memory_repo.get_storage_size_bytes.return_value = 10 * 1024 * 1024

        status = await self.service._check_scope_quota(self.tenant_id, MemoryScope.DURABLE)

        assert status.is_over_quota is True
        assert "Record count 100 exceeds limit 100" in status.quota_exceeded_reason

    @pytest.mark.asyncio
    async def test_check_scope_quota_exceeded_storage(self) -> None:
        policy = MemoryRetentionPolicy(
            id=uuid4(),
            tenant_id=self.tenant_id,
            scope=MemoryScope.DURABLE,
            retention_days=30,
            max_storage_mb=50,
        )
        self.retention_repo.get_by_tenant_scope.return_value = policy
        self.memory_repo.count_by_tenant.return_value = 50
        self.memory_repo.get_storage_size_bytes.return_value = 60 * 1024 * 1024

        status = await self.service._check_scope_quota(self.tenant_id, MemoryScope.DURABLE)

        assert status.is_over_quota is True
        assert "Storage 60MB exceeds limit 50MB" in status.quota_exceeded_reason

    @pytest.mark.asyncio
    async def test_check_scope_quota_ok(self) -> None:
        policy = MemoryRetentionPolicy(
            id=uuid4(),
            tenant_id=self.tenant_id,
            scope=MemoryScope.DURABLE,
            retention_days=30,
            max_records_per_tenant=1000,
            max_storage_mb=100,
        )
        self.retention_repo.get_by_tenant_scope.return_value = policy
        self.memory_repo.count_by_tenant.return_value = 100
        self.memory_repo.get_storage_size_bytes.return_value = 50 * 1024 * 1024

        status = await self.service._check_scope_quota(self.tenant_id, MemoryScope.DURABLE)

        assert status.is_over_quota is False

    @pytest.mark.asyncio
    async def test_enforce_quotas(self) -> None:
        policy = MemoryRetentionPolicy(
            id=uuid4(),
            tenant_id=self.tenant_id,
            scope=MemoryScope.DURABLE,
            retention_days=30,
            max_records_per_tenant=1000,
        )
        self.retention_repo.get_by_tenant_scope.return_value = policy
        self.memory_repo.count_by_tenant.return_value = 100
        self.memory_repo.get_storage_size_bytes.return_value = 10 * 1024 * 1024

        statuses = await self.service.enforce_quotas(self.tenant_id)

        assert len(statuses) == 3
        assert all(isinstance(s, QuotaStatus) for s in statuses)

    @pytest.mark.asyncio
    async def test_get_quota_status(self) -> None:
        self.retention_repo.get_by_tenant_scope.return_value = None
        self.memory_repo.count_by_tenant.return_value = 10
        self.memory_repo.get_storage_size_bytes.return_value = 1024 * 1024

        statuses = await self.service.get_quota_status(self.tenant_id)

        assert len(statuses) == 3

    @pytest.mark.asyncio
    async def test_run_full_cleanup(self) -> None:
        self.memory_repo.delete_expired.return_value = 10
        # Provide enough values for all get_storage_size_bytes calls:
        # cleanup_expired: 3 scopes * 2 = 6
        # enforce_retention_policies: 3 scopes * 2 = 6
        # enforce_quotas: 3 scopes * 1 = 3
        # Total: 15 calls
        storage_values = []
        for _ in range(15):
            storage_values.append(2000000)
            storage_values.append(1500000)
        self.memory_repo.get_storage_size_bytes.side_effect = storage_values
        
        self.retention_repo.get_by_tenant_scope.return_value = None
        self.memory_repo.count_by_tenant.return_value = 50

        result = await self.service.run_full_cleanup(self.tenant_id)

        assert result["tenant_id"] == str(self.tenant_id)
        assert "expired_cleanup" in result
        assert "retention_enforcement" in result
        assert "quota_status" in result
        assert "total_duration_ms" in result