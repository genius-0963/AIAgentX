"""Rate limiting service for API and resource protection."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING
from uuid import UUID

from app.infrastructure.observability.logging import get_logger

if TYPE_CHECKING:
    from app.infrastructure.cache.rate_limiter import RateLimiter

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class RateLimitResult:
    """Result of rate limit check."""

    allowed: bool
    remaining: int = 0
    reset_at: int = 0
    limit: int = 0
    reason: str | None = None


class RateLimitService:
    """Service for rate limiting and concurrency control."""

    def __init__(
        self,
        rate_limiter: RateLimiter,
        default_limits: dict[str, dict[str, int]] | None = None,
    ) -> None:
        """Initialize rate limit service.

        Args:
            rate_limiter: Redis-based rate limiter
            default_limits: Default rate limits per plan
        """
        self._rate_limiter = rate_limiter
        self._default_limits = default_limits or {
            "free": {"requests_per_minute": 60, "concurrent_runs": 5},
            "starter": {"requests_per_minute": 120, "concurrent_runs": 20},
            "professional": {"requests_per_minute": 300, "concurrent_runs": 50},
            "enterprise": {"requests_per_minute": 600, "concurrent_runs": 100},
        }

    async def check_rate_limit(
        self,
        tenant_id: UUID,
        endpoint: str,
        plan: str = "free",
    ) -> RateLimitResult:
        """Check if tenant is within rate limits.

        Args:
            tenant_id: Tenant ID
            endpoint: API endpoint being accessed
            plan: Tenant plan for limit configuration

        Returns:
            RateLimitResult with allowance status and details
        """
        limits = self._default_limits.get(plan, self._default_limits["free"])
        requests_per_minute = limits.get("requests_per_minute", 60)

        try:
            result = await self._rate_limiter.check_rate_limit(
                key=f"tenant:{tenant_id}:{endpoint}",
                limit=requests_per_minute,
                window_seconds=60,
            )

            if result["allowed"]:
                return RateLimitResult(
                    allowed=True,
                    remaining=result["remaining"],
                    reset_at=result["reset_at"],
                    limit=requests_per_minute,
                )
            return RateLimitResult(
                allowed=False,
                remaining=0,
                reset_at=result["reset_at"],
                limit=requests_per_minute,
                reason="Rate limit exceeded",
            )

        except Exception as e:
            logger.error(
                "Rate limit check failed",
                extra={"tenant_id": str(tenant_id), "endpoint": endpoint, "error": str(e)},
            )
            # Fail open - allow request if rate limiting fails
            return RateLimitResult(
                allowed=True,
                remaining=requests_per_minute,
                limit=requests_per_minute,
            )

    async def check_concurrent_runs(
        self,
        tenant_id: UUID,
        plan: str = "free",
    ) -> RateLimitResult:
        """Check if tenant is within concurrent run limits.

        Args:
            tenant_id: Tenant ID
            plan: Tenant plan for limit configuration

        Returns:
            RateLimitResult with allowance status and details
        """
        limits = self._default_limits.get(plan, self._default_limits["free"])
        max_concurrent = limits.get("concurrent_runs", 5)

        try:
            result = await self._rate_limiter.check_concurrency(
                key=f"tenant:{tenant_id}:concurrent_runs",
                limit=max_concurrent,
            )

            if result["allowed"]:
                return RateLimitResult(
                    allowed=True,
                    remaining=result["remaining"],
                    limit=max_concurrent,
                )
            return RateLimitResult(
                allowed=False,
                remaining=0,
                limit=max_concurrent,
                reason="Concurrent run limit exceeded",
            )

        except Exception as e:
            logger.error(
                "Concurrent run check failed",
                extra={"tenant_id": str(tenant_id), "error": str(e)},
            )
            # Fail open - allow request if concurrency check fails
            return RateLimitResult(allowed=True, remaining=max_concurrent, limit=max_concurrent)

    async def check_global_concurrency(self, global_limit: int = 1000) -> RateLimitResult:
        """Check if system is within global concurrency limits.

        Args:
            global_limit: Global concurrent run limit

        Returns:
            RateLimitResult with allowance status and details
        """
        try:
            result = await self._rate_limiter.check_concurrency(
                key="global:concurrent_runs",
                limit=global_limit,
            )

            if result["allowed"]:
                return RateLimitResult(
                    allowed=True,
                    remaining=result["remaining"],
                    limit=global_limit,
                )
            return RateLimitResult(
                allowed=False,
                remaining=0,
                limit=global_limit,
                reason="Global concurrency limit exceeded",
            )

        except Exception as e:
            logger.error("Global concurrency check failed", extra={"error": str(e)})
            # Fail open - allow request if global check fails
            return RateLimitResult(allowed=True, remaining=global_limit, limit=global_limit)

    async def record_request(self, tenant_id: UUID, endpoint: str) -> None:
        """Record a request for rate limiting.

        Args:
            tenant_id: Tenant ID
            endpoint: API endpoint accessed
        """
        try:
            await self._rate_limiter.record_request(
                key=f"tenant:{tenant_id}:{endpoint}",
                window_seconds=60,
            )
        except Exception as e:
            logger.error(
                "Failed to record request",
                extra={"tenant_id": str(tenant_id), "endpoint": endpoint, "error": str(e)},
            )

    async def record_run_start(self, tenant_id: UUID) -> None:
        """Record a run start for concurrency tracking.

        Args:
            tenant_id: Tenant ID starting a run
        """
        try:
            await self._rate_limiter.increment_concurrency(
                key=f"tenant:{tenant_id}:concurrent_runs"
            )
            await self._rate_limiter.increment_concurrency(key="global:concurrent_runs")
        except Exception as e:
            logger.error(
                "Failed to record run start",
                extra={"tenant_id": str(tenant_id), "error": str(e)},
            )

    async def record_run_end(self, tenant_id: UUID) -> None:
        """Record a run end for concurrency tracking.

        Args:
            tenant_id: Tenant ID ending a run
        """
        try:
            await self._rate_limiter.decrement_concurrency(
                key=f"tenant:{tenant_id}:concurrent_runs"
            )
            await self._rate_limiter.decrement_concurrency(key="global:concurrent_runs")
        except Exception as e:
            logger.error(
                "Failed to record run end",
                extra={"tenant_id": str(tenant_id), "error": str(e)},
            )

    async def get_rate_limit_headers(
        self,
        tenant_id: UUID,
        endpoint: str,
        plan: str = "free",
    ) -> dict[str, str]:
        """Get rate limit headers for response.

        Args:
            tenant_id: Tenant ID
            endpoint: API endpoint
            plan: Tenant plan

        Returns:
            Dictionary with rate limit headers
        """
        limits = self._default_limits.get(plan, self._default_limits["free"])
        limit = limits.get("requests_per_minute", 60)

        try:
            result = await self._rate_limiter.get_current_usage(
                key=f"tenant:{tenant_id}:{endpoint}",
                window_seconds=60,
            )

            return {
                "X-RateLimit-Limit": str(limit),
                "X-RateLimit-Remaining": str(result["remaining"]),
                "X-RateLimit-Reset": str(result["reset_at"]),
            }
        except Exception as e:
            logger.error(
                "Failed to get rate limit headers",
                extra={"tenant_id": str(tenant_id), "endpoint": endpoint, "error": str(e)},
            )
            return {
                "X-RateLimit-Limit": str(limit),
                "X-RateLimit-Remaining": str(limit),
                "X-RateLimit-Reset": "0",
            }

    def update_plan_limits(self, plan: str, limits: dict[str, int]) -> None:
        """Update rate limits for a plan.

        Args:
            plan: Plan name
            limits: New limits dictionary
        """
        self._default_limits[plan] = limits
        logger.info(
            "Rate limits updated for plan",
            extra={"plan": plan, "limits": limits},
        )

    async def health_check(self) -> bool:
        """Check if rate limiting service is healthy.

        Returns:
            True if healthy, False otherwise
        """
        try:
            return await self._rate_limiter.health_check()
        except Exception as e:
            logger.error("Rate limit service health check failed", extra={"error": str(e)})
            return False
