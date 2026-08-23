"""Redis-based budget caching for fast budget checks."""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.infrastructure.observability.logging import get_logger

if TYPE_CHECKING:
    from redis.asyncio import Redis

logger = get_logger(__name__)


class BudgetCache:
    """Redis-based cache for budget tracking to enable fast checks."""

    def __init__(self, redis_client: Redis[str], ttl_seconds: int = 300) -> None:
        """Initialize budget cache.

        Args:
            redis_client: Redis client instance
            ttl_seconds: Time-to-live for cached budget data (default 5 minutes)
        """
        self._redis = redis_client
        self._ttl = ttl_seconds

    def _run_budget_key(self, run_id: str) -> str:
        """Generate Redis key for run budget data."""
        return f"budget:run:{run_id}"

    def _tenant_budget_key(self, tenant_id: str, budget_type: str) -> str:
        """Generate Redis key for tenant budget data."""
        return f"budget:tenant:{tenant_id}:{budget_type}"

    async def get_run_budget(self, run_id: str) -> dict[str, int] | None:
        """Get cached budget data for a run.

        Args:
            run_id: Run ID as string

        Returns:
            Dictionary with budget data or None if not cached
        """
        key = self._run_budget_key(run_id)
        try:
            data = await self._redis.hgetall(key)
            if not data:
                return None

            return {
                "max_cost_microunits": int(data.get("max_cost", 0)),
                "spent_cost_microunits": int(data.get("spent", 0)),
                "max_steps": int(data.get("max_steps", 0)),
                "current_steps": int(data.get("current_steps", 0)),
                "timeout_seconds": int(data.get("timeout", 90)),
            }
        except Exception as e:
            logger.error(
                "Failed to get run budget from cache",
                extra={"run_id": run_id, "error": str(e)},
            )
            return None

    async def set_run_budget(
        self,
        run_id: str,
        max_cost_microunits: int,
        spent_cost_microunits: int,
        max_steps: int,
        current_steps: int,
        timeout_seconds: int = 90,
    ) -> bool:
        """Cache budget data for a run.

        Args:
            run_id: Run ID as string
            max_cost_microunits: Maximum cost in micro-units
            spent_cost_microunits: Spent cost in micro-units
            max_steps: Maximum number of steps
            current_steps: Current number of steps
            timeout_seconds: Timeout in seconds

        Returns:
            True if cache was set successfully, False otherwise
        """
        key = self._run_budget_key(run_id)
        try:
            await self._redis.hset(
                key,
                mapping={
                    "max_cost": str(max_cost_microunits),
                    "spent": str(spent_cost_microunits),
                    "max_steps": str(max_steps),
                    "current_steps": str(current_steps),
                    "timeout": str(timeout_seconds),
                },
            )
            await self._redis.expire(key, self._ttl)
            return True
        except Exception as e:
            logger.error(
                "Failed to set run budget in cache",
                extra={"run_id": run_id, "error": str(e)},
            )
            return False

    async def increment_run_spent(self, run_id: str, amount_microunits: int) -> bool:
        """Increment spent cost for a run in cache.

        Args:
            run_id: Run ID as string
            amount_microunits: Amount to increment in micro-units

        Returns:
            True if increment was successful, False otherwise
        """
        key = self._run_budget_key(run_id)
        try:
            await self._redis.hincrby(key, "spent", amount_microunits)
            await self._redis.expire(key, self._ttl)
            return True
        except Exception as e:
            logger.error(
                "Failed to increment run spent in cache",
                extra={"run_id": run_id, "amount": amount_microunits, "error": str(e)},
            )
            return False

    async def increment_run_steps(self, run_id: str) -> bool:
        """Increment step count for a run in cache.

        Args:
            run_id: Run ID as string

        Returns:
            True if increment was successful, False otherwise
        """
        key = self._run_budget_key(run_id)
        try:
            await self._redis.hincrby(key, "current_steps", 1)
            await self._redis.expire(key, self._ttl)
            return True
        except Exception as e:
            logger.error(
                "Failed to increment run steps in cache",
                extra={"run_id": run_id, "error": str(e)},
            )
            return False

    async def get_tenant_budget(self, tenant_id: str, budget_type: str) -> dict[str, float] | None:
        """Get cached budget data for a tenant.

        Args:
            tenant_id: Tenant ID as string
            budget_type: Type of budget ("daily" or "monthly")

        Returns:
            Dictionary with budget data or None if not cached
        """
        key = self._tenant_budget_key(tenant_id, budget_type)
        try:
            data = await self._redis.hgetall(key)
            if not data:
                return None

            return {
                "max_budget_usd": float(data.get("max", 0)),
                "spent_budget_usd": float(data.get("spent", 0)),
            }
        except Exception as e:
            logger.error(
                "Failed to get tenant budget from cache",
                extra={"tenant_id": tenant_id, "budget_type": budget_type, "error": str(e)},
            )
            return None

    async def set_tenant_budget(
        self,
        tenant_id: str,
        budget_type: str,
        max_budget_usd: float,
        spent_budget_usd: float,
    ) -> bool:
        """Cache budget data for a tenant.

        Args:
            tenant_id: Tenant ID as string
            budget_type: Type of budget ("daily" or "monthly")
            max_budget_usd: Maximum budget in USD
            spent_budget_usd: Spent budget in USD

        Returns:
            True if cache was set successfully, False otherwise
        """
        key = self._tenant_budget_key(tenant_id, budget_type)
        try:
            await self._redis.hset(
                key,
                mapping={
                    "max": str(max_budget_usd),
                    "spent": str(spent_budget_usd),
                },
            )
            await self._redis.expire(key, self._ttl)
            return True
        except Exception as e:
            logger.error(
                "Failed to set tenant budget in cache",
                extra={"tenant_id": tenant_id, "budget_type": budget_type, "error": str(e)},
            )
            return False

    async def increment_tenant_spent(
        self,
        tenant_id: str,
        budget_type: str,
        amount_usd: float,
    ) -> bool:
        """Increment spent budget for a tenant in cache.

        Args:
            tenant_id: Tenant ID as string
            budget_type: Type of budget ("daily" or "monthly")
            amount_usd: Amount to increment in USD

        Returns:
            True if increment was successful, False otherwise
        """
        key = self._tenant_budget_key(tenant_id, budget_type)
        try:
            # Redis doesn't support float hincrby, so we get, increment, set
            current = await self._redis.hget(key, "spent")
            current_float = float(current) if current else 0.0
            new_value = current_float + amount_usd
            await self._redis.hset(key, "spent", str(new_value))
            await self._redis.expire(key, self._ttl)
            return True
        except Exception as e:
            logger.error(
                "Failed to increment tenant spent in cache",
                extra={
                    "tenant_id": tenant_id,
                    "budget_type": budget_type,
                    "amount": amount_usd,
                    "error": str(e),
                },
            )
            return False

    async def invalidate_run(self, run_id: str) -> bool:
        """Invalidate cached budget data for a run.

        Args:
            run_id: Run ID as string

        Returns:
            True if invalidation was successful, False otherwise
        """
        key = self._run_budget_key(run_id)
        try:
            await self._redis.delete(key)
            return True
        except Exception as e:
            logger.error(
                "Failed to invalidate run budget cache",
                extra={"run_id": run_id, "error": str(e)},
            )
            return False

    async def invalidate_tenant(self, tenant_id: str, budget_type: str | None = None) -> bool:
        """Invalidate cached budget data for a tenant.

        Args:
            tenant_id: Tenant ID as string
            budget_type: Specific budget type to invalidate, or None for all

        Returns:
            True if invalidation was successful, False otherwise
        """
        try:
            if budget_type:
                key = self._tenant_budget_key(tenant_id, budget_type)
                await self._redis.delete(key)
            else:
                # Invalidate all budget types for tenant
                for bt in ["daily", "monthly"]:
                    key = self._tenant_budget_key(tenant_id, bt)
                    await self._redis.delete(key)
            return True
        except Exception as e:
            logger.error(
                "Failed to invalidate tenant budget cache",
                extra={"tenant_id": tenant_id, "budget_type": budget_type, "error": str(e)},
            )
            return False

    async def health_check(self) -> bool:
        """Check if budget cache is healthy.

        Returns:
            True if cache is healthy, False otherwise
        """
        try:
            await self._redis.ping()
            return True
        except Exception as e:
            logger.error("Budget cache health check failed", extra={"error": str(e)})
            return False
