"""Usage tracking SQL repository implementation."""

from __future__ import annotations

import time
from typing import Any
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.providers.value_objects import UsageRecord
from app.domain.repositories.usage import UsageRepository
from app.infrastructure.observability.logging import get_logger

logger = get_logger(__name__)


class SQLUsageRepository(UsageRepository):
    """SQL implementation of usage tracking repository."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def record_usage(self, usage: UsageRecord) -> UsageRecord:
        """Record a single usage record.

        Args:
            usage: The usage record to persist

        Returns:
            The persisted usage record
        """
        from app.infrastructure.db.models.run import RunStepModel

        # Find the run step by request_id (assuming request_id maps to a step)
        # In a real implementation, we'd need a better way to map request_id to step
        # For now, we'll just log the usage record
        logger.info(
            "Usage record",
            extra={
                "provider": usage.provider,
                "model": usage.model,
                "prompt_tokens": usage.prompt_tokens,
                "completion_tokens": usage.completion_tokens,
                "total_tokens": usage.total_tokens,
                "cost_microunits": usage.cost_microunits,
                "request_id": usage.request_id,
            },
        )

        # In a real implementation, we would update the run step with usage data
        # For now, we'll return the usage record as-is
        return usage

    async def record_usage_batch(self, usage_records: list[UsageRecord]) -> list[UsageRecord]:
        """Record multiple usage records in a batch.

        Args:
            usage_records: List of usage records to persist

        Returns:
            List of persisted usage records
        """
        logger.info(
            "Batch usage records",
            extra={"count": len(usage_records)},
        )

        # In a real implementation, we would batch insert into usage_summaries table
        # For now, we'll return the usage records as-is
        return usage_records

    async def get_usage_by_run_id(self, run_id: UUID) -> list[UsageRecord]:
        """Get all usage records for a specific run.

        Args:
            run_id: The run ID to fetch usage for

        Returns:
            List of usage records for the run
        """
        from app.infrastructure.db.models.run import RunStepModel

        query = select(RunStepModel).where(RunStepModel.run_id == run_id)
        result = await self._session.execute(query)
        steps = result.scalars().all()

        usage_records = []
        for step in steps:
            if step.provider and step.model:
                usage_record = UsageRecord(
                    provider=step.provider,
                    model=step.model,
                    prompt_tokens=step.prompt_tokens or 0,
                    completion_tokens=step.completion_tokens or 0,
                    total_tokens=step.total_tokens or 0,
                    cost_microunits=step.cost_microunits or 0,
                    timestamp=step.created_at.timestamp() if step.created_at else time.time(),
                    request_id=str(step.id),  # Use step ID as request_id
                )
                usage_records.append(usage_record)

        return usage_records

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
        from app.infrastructure.db.models.run import RunModel, RunStepModel

        query = (
            select(RunStepModel)
            .join(RunModel, RunStepModel.run_id == RunModel.id)
            .where(RunModel.tenant_id == tenant_id)
        )

        if start_timestamp:
            start_datetime = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(start_timestamp))
            query = query.where(RunStepModel.created_at >= start_datetime)

        if end_timestamp:
            end_datetime = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(end_timestamp))
            query = query.where(RunStepModel.created_at <= end_datetime)

        result = await self._session.execute(query)
        steps = result.scalars().all()

        usage_records = []
        for step in steps:
            if step.provider and step.model:
                usage_record = UsageRecord(
                    provider=step.provider,
                    model=step.model,
                    prompt_tokens=step.prompt_tokens or 0,
                    completion_tokens=step.completion_tokens or 0,
                    total_tokens=step.total_tokens or 0,
                    cost_microunits=step.cost_microunits or 0,
                    timestamp=step.created_at.timestamp() if step.created_at else time.time(),
                    request_id=str(step.id),
                )
                usage_records.append(usage_record)

        return usage_records

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
            Dictionary with aggregated statistics
        """
        from app.infrastructure.db.models.run import RunModel, RunStepModel

        # Build base query
        query = (
            select(
                func.sum(RunStepModel.prompt_tokens).label("total_prompt_tokens"),
                func.sum(RunStepModel.completion_tokens).label("total_completion_tokens"),
                func.sum(RunStepModel.total_tokens).label("total_tokens"),
                func.sum(RunStepModel.cost_microunits).label("total_cost_microunits"),
                func.count(RunStepModel.id).label("total_requests"),
            )
            .join(RunModel, RunStepModel.run_id == RunModel.id)
            .where(RunModel.tenant_id == tenant_id)
        )

        # Apply filters
        if provider:
            query = query.where(RunStepModel.provider == provider)
        if model:
            query = query.where(RunStepModel.model == model)
        if start_timestamp:
            start_datetime = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(start_timestamp))
            query = query.where(RunStepModel.created_at >= start_datetime)
        if end_timestamp:
            end_datetime = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(end_timestamp))
            query = query.where(RunStepModel.created_at <= end_datetime)

        result = await self._session.execute(query)
        row = result.one()

        # Get aggregation by provider
        by_provider_query = (
            select(
                RunStepModel.provider,
                func.sum(RunStepModel.total_tokens).label("tokens"),
                func.sum(RunStepModel.cost_microunits).label("cost"),
            )
            .join(RunModel, RunStepModel.run_id == RunModel.id)
            .where(RunModel.tenant_id == tenant_id)
            .group_by(RunStepModel.provider)
        )

        if provider:
            by_provider_query = by_provider_query.where(RunStepModel.provider == provider)

        by_provider_result = await self._session.execute(by_provider_query)
        by_provider = {row.provider: {"tokens": row.tokens, "cost": row.cost} for row in by_provider_result}

        # Get aggregation by model
        by_model_query = (
            select(
                RunStepModel.model,
                func.sum(RunStepModel.total_tokens).label("tokens"),
                func.sum(RunStepModel.cost_microunits).label("cost"),
            )
            .join(RunModel, RunStepModel.run_id == RunModel.id)
            .where(RunModel.tenant_id == tenant_id)
            .group_by(RunStepModel.model)
        )

        if model:
            by_model_query = by_model_query.where(RunStepModel.model == model)

        by_model_result = await self._session.execute(by_model_query)
        by_model = {row.model: {"tokens": row.tokens, "cost": row.cost} for row in by_model_result}

        return {
            "total_tokens": row.total_tokens or 0,
            "total_cost_microunits": row.total_cost_microunits or 0,
            "total_requests": row.total_requests or 0,
            "by_provider": by_provider,
            "by_model": by_model,
        }
