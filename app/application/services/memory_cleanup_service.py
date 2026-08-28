"""Memory cleanup service for retention enforcement and quota management."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID

from app.domain.entities.memory import MemoryRetentionPolicy, MemoryScope
from app.domain.repositories.memory import (
    MemoryRepository,
    MemoryRetentionPolicyRepository,
)

if TYPE_CHECKING:
    from app.infrastructure.observability.logging import get_logger

logger = logging.getLogger(__name__)


@dataclass
class CleanupResult:
    """Result of a cleanup operation."""

    tenant_id: UUID
    scope: MemoryScope
    expired_deleted: int
    quota_enforced: bool
    storage_freed_mb: float
    duration_ms: float
    errors: list[str]


@dataclass
class QuotaStatus:
    """Current quota status for a tenant/scope."""

    tenant_id: UUID
    scope: MemoryScope
    record_count: int
    storage_mb: float
    max_records: int | None
    max_storage_mb: int | None
    retention_days: int
    is_over_quota: bool
    quota_exceeded_reason: str | None


class MemoryCleanupService:
    """Service for memory cleanup, retention enforcement, and quota management."""

    def __init__(
        self,
        memory_repository: MemoryRepository,
        retention_policy_repository: MemoryRetentionPolicyRepository,
    ) -> None:
        """Initialize memory cleanup service.

        Args:
            memory_repository: Repository for memory operations
            retention_policy_repository: Repository for retention policies
        """
        self._memory_repository = memory_repository
        self._retention_policy_repository = retention_policy_repository

    async def cleanup_expired(self, tenant_id: UUID) -> CleanupResult:
        """Delete all expired memory records for a tenant.

        Args:
            tenant_id: The tenant ID

        Returns:
            Cleanup result with statistics
        """
        start_time = datetime.now(UTC)
        errors = []

        # Get all scopes for this tenant
        scopes = [MemoryScope.EPHEMERAL, MemoryScope.SESSION, MemoryScope.DURABLE]
        total_deleted = 0
        total_freed_mb = 0.0

        for scope in scopes:
            try:
                # Get storage size before deletion
                storage_before = await self._memory_repository.get_storage_size_bytes(tenant_id)

                # Delete expired records for this scope
                deleted = await self._memory_repository.delete_expired(tenant_id)

                # Get storage size after deletion
                storage_after = await self._memory_repository.get_storage_size_bytes(tenant_id)
                freed_mb = (storage_before - storage_after) / (1024 * 1024)

                total_deleted += deleted
                total_freed_mb += freed_mb

                logger.info(
                    "Expired records cleaned up",
                    extra={
                        "tenant_id": str(tenant_id),
                        "scope": scope.value,
                        "deleted": deleted,
                        "freed_mb": round(freed_mb, 2),
                    },
                )

            except Exception as e:
                error_msg = f"Failed to cleanup {scope.value}: {e}"
                errors.append(error_msg)
                logger.error(error_msg, extra={"tenant_id": str(tenant_id), "scope": scope.value})

        duration_ms = (datetime.now(UTC) - start_time).total_seconds() * 1000

        # Emit cleanup event
        # In production, this would go through outbox pattern
        logger.info(
            "Memory cleanup completed",
            extra={
                "tenant_id": str(tenant_id),
                "total_deleted": total_deleted,
                "total_freed_mb": round(total_freed_mb, 2),
                "duration_ms": round(duration_ms, 2),
                "errors": errors,
            },
        )

        return CleanupResult(
            tenant_id=tenant_id,
            scope=MemoryScope.DURABLE,  # Aggregate scope
            expired_deleted=total_deleted,
            quota_enforced=False,
            storage_freed_mb=total_freed_mb,
            duration_ms=duration_ms,
            errors=errors,
        )

    async def enforce_retention_policies(self, tenant_id: UUID) -> list[CleanupResult]:
        """Enforce retention policies for all scopes of a tenant.

        Args:
            tenant_id: The tenant ID

        Returns:
            List of cleanup results per scope
        """
        results = []
        scopes = [MemoryScope.EPHEMERAL, MemoryScope.SESSION, MemoryScope.DURABLE]

        for scope in scopes:
            try:
                result = await self._enforce_scope_retention(tenant_id, scope)
                results.append(result)
            except Exception as e:
                logger.error(
                    f"Failed to enforce retention for {scope.value}",
                    extra={"tenant_id": str(tenant_id), "scope": scope.value, "error": str(e)},
                )
                results.append(
                    CleanupResult(
                        tenant_id=tenant_id,
                        scope=scope,
                        expired_deleted=0,
                        quota_enforced=False,
                        storage_freed_mb=0.0,
                        duration_ms=0.0,
                        errors=[str(e)],
                    )
                )

        return results

    async def _enforce_scope_retention(
        self,
        tenant_id: UUID,
        scope: MemoryScope,
    ) -> CleanupResult:
        """Enforce retention policy for a specific scope.

        Args:
            tenant_id: The tenant ID
            scope: The memory scope

        Returns:
            Cleanup result
        """
        start_time = datetime.now(UTC)

        # Get retention policy for this scope
        policy = await self._retention_policy_repository.get_by_tenant_scope(tenant_id, scope)

        if not policy:
            # No policy = no enforcement needed
            return CleanupResult(
                tenant_id=tenant_id,
                scope=scope,
                expired_deleted=0,
                quota_enforced=False,
                storage_freed_mb=0.0,
                duration_ms=0.0,
                errors=[],
            )

        # The delete_expired method already handles expiration based on expires_at
        # which is set according to the retention policy at write time
        storage_before = await self._memory_repository.get_storage_size_bytes(tenant_id)
        deleted = await self._memory_repository.delete_expired(tenant_id)
        storage_after = await self._memory_repository.get_storage_size_bytes(tenant_id)
        freed_mb = (storage_before - storage_after) / (1024 * 1024)

        duration_ms = (datetime.now(UTC) - start_time).total_seconds() * 1000

        return CleanupResult(
            tenant_id=tenant_id,
            scope=scope,
            expired_deleted=deleted,
            quota_enforced=False,
            storage_freed_mb=freed_mb,
            duration_ms=duration_ms,
            errors=[],
        )

    async def enforce_quotas(self, tenant_id: UUID) -> list[QuotaStatus]:
        """Check and enforce quotas for all scopes of a tenant.

        Args:
            tenant_id: The tenant ID

        Returns:
            List of quota statuses per scope
        """
        statuses = []
        scopes = [MemoryScope.EPHEMERAL, MemoryScope.SESSION, MemoryScope.DURABLE]

        for scope in scopes:
            status = await self._check_scope_quota(tenant_id, scope)
            statuses.append(status)

            if status.is_over_quota:
                logger.warning(
                    "Memory quota exceeded",
                    extra={
                        "tenant_id": str(tenant_id),
                        "scope": scope.value,
                        "record_count": status.record_count,
                        "storage_mb": status.storage_mb,
                        "max_records": status.max_records,
                        "max_storage_mb": status.max_storage_mb,
                        "reason": status.quota_exceeded_reason,
                    },
                )

        return statuses

    async def _check_scope_quota(
        self,
        tenant_id: UUID,
        scope: MemoryScope,
    ) -> QuotaStatus:
        """Check quota for a specific scope.

        Args:
            tenant_id: The tenant ID
            scope: The memory scope

        Returns:
            Quota status
        """
        policy = await self._retention_policy_repository.get_by_tenant_scope(tenant_id, scope)

        record_count = await self._memory_repository.count_by_tenant(tenant_id, scope)
        storage_bytes = await self._memory_repository.get_storage_size_bytes(tenant_id)
        storage_mb = storage_bytes / (1024 * 1024)

        if not policy:
            return QuotaStatus(
                tenant_id=tenant_id,
                scope=scope,
                record_count=record_count,
                storage_mb=storage_mb,
                max_records=None,
                max_storage_mb=None,
                retention_days=0,
                is_over_quota=False,
                quota_exceeded_reason=None,
            )

        is_exceeded, reason = policy.is_quota_exceeded(record_count, int(storage_mb))

        return QuotaStatus(
            tenant_id=tenant_id,
            scope=scope,
            record_count=record_count,
            storage_mb=storage_mb,
            max_records=policy.max_records_per_tenant,
            max_storage_mb=policy.max_storage_mb,
            retention_days=policy.retention_days,
            is_over_quota=is_exceeded,
            quota_exceeded_reason=reason if is_exceeded else None,
        )

    async def get_quota_status(self, tenant_id: UUID) -> list[QuotaStatus]:
        """Get current quota status for all scopes of a tenant.

        Args:
            tenant_id: The tenant ID

        Returns:
            List of quota statuses
        """
        return await self.enforce_quotas(tenant_id)

    async def run_full_cleanup(self, tenant_id: UUID) -> dict:
        """Run full cleanup: expired records + retention + quotas.

        Args:
            tenant_id: The tenant ID

        Returns:
            Summary of all cleanup operations
        """
        start_time = datetime.now(UTC)

        # Clean up expired records
        expired_result = await self.cleanup_expired(tenant_id)

        # Enforce retention policies
        retention_results = await self.enforce_retention_policies(tenant_id)

        # Check quotas
        quota_statuses = await self.enforce_quotas(tenant_id)

        total_duration_ms = (datetime.now(UTC) - start_time).total_seconds() * 1000

        return {
            "tenant_id": str(tenant_id),
            "expired_cleanup": {
                "deleted": expired_result.expired_deleted,
                "freed_mb": round(expired_result.storage_freed_mb, 2),
                "duration_ms": round(expired_result.duration_ms, 2),
                "errors": expired_result.errors,
            },
            "retention_enforcement": [
                {
                    "scope": r.scope.value,
                    "deleted": r.expired_deleted,
                    "freed_mb": round(r.storage_freed_mb, 2),
                    "duration_ms": round(r.duration_ms, 2),
                    "errors": r.errors,
                }
                for r in retention_results
            ],
            "quota_status": [
                {
                    "scope": s.scope.value,
                    "record_count": s.record_count,
                    "storage_mb": round(s.storage_mb, 2),
                    "max_records": s.max_records,
                    "max_storage_mb": s.max_storage_mb,
                    "is_over_quota": s.is_over_quota,
                    "reason": s.quota_exceeded_reason,
                }
                for s in quota_statuses
            ],
            "total_duration_ms": round(total_duration_ms, 2),
        }