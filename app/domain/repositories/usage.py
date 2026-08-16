"""Usage tracking repository protocol."""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from app.domain.providers.value_objects import UsageRecord


class UsageRepository(Protocol):
    """Repository for usage tracking operations."""

    async def record_usage(self, usage: UsageRecord) -> UsageRecord:
        """Record a single usage record.

        Args:
            usage: The usage record to persist

        Returns:
            The persisted usage record
        """
        ...

    async def record_usage_batch(self, usage_records: list[UsageRecord]) -> list[UsageRecord]:
        """Record multiple usage records in a batch.

        Args:
            usage_records: List of usage records to persist

        Returns:
            List of persisted usage records
        """
        ...

    async def get_usage_by_run_id(self, run_id: UUID) -> list[UsageRecord]:
        """Get all usage records for a specific run.

        Args:
            run_id: The run ID to fetch usage for

        Returns:
            List of usage records for the run
        """
        ...

    async def get_usage_by_tenant(
        self,
        tenant_id: UUID,
        start_timestamp: float | None = None,
        end_timestamp: float | None = None,
    ) -> list[UsageRecord]:
        """Get usage records for a tenant within a time range.

        Args:
            tenant_id: The tenant ID to fetch usage for
            start_timestamp: Optional start timestamp (Unix)
            end_timestamp: Optional end timestamp (Unix)

        Returns:
            List of usage records for the tenant
        """
        ...

    async def get_aggregated_usage(
        self,
        tenant_id: UUID,
        provider: str | None = None,
        model: str | None = None,
        start_timestamp: float | None = None,
        end_timestamp: float | None = None,
    ) -> dict[str, Any]:
        """Get aggregated usage statistics.

        Args:
            tenant_id: The tenant ID to aggregate usage for
            provider: Optional provider filter
            model: Optional model filter
            start_timestamp: Optional start timestamp (Unix)
            end_timestamp: Optional end timestamp (Unix)

        Returns:
            Dictionary with aggregated statistics:
            {
                "total_tokens": int,
                "total_cost_microunits": int,
                "total_requests": int,
                "by_provider": dict,
                "by_model": dict
            }
        """
        ...
