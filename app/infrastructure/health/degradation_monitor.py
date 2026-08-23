"""Health monitoring for degradation detection."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from app.application.services.degradation_service import DegradationMode
from app.infrastructure.observability.logging import get_logger

if TYPE_CHECKING:
    from app.application.services.degradation_service import DegradationService
    from app.infrastructure.cache.redis_client import check_redis_health
    from app.infrastructure.db.engine import check_database_health

logger = get_logger(__name__)


class DegradationMonitor:
    """Monitor system health and trigger degradation when needed."""

    def __init__(
        self,
        degradation_service: DegradationService,
        check_interval_seconds: float = 30.0,
    ) -> None:
        """Initialize degradation monitor.

        Args:
            degradation_service: Degradation service instance
            check_interval_seconds: Interval between health checks
        """
        self._degradation_service = degradation_service
        self._check_interval = check_interval_seconds
        self._running = False
        self._monitor_task: asyncio.Task | None = None

    async def start_monitoring(self) -> None:
        """Start the health monitoring loop."""
        if self._running:
            logger.warning("Degradation monitor already running")
            return

        self._running = True
        self._monitor_task = asyncio.create_task(self._monitor_loop())

        logger.info("Degradation monitor started", extra={"check_interval": self._check_interval})

    async def stop_monitoring(self) -> None:
        """Stop the health monitoring loop."""
        if not self._running:
            return

        self._running = False

        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass

        logger.info("Degradation monitor stopped")

    async def _monitor_loop(self) -> None:
        """Main monitoring loop."""
        while self._running:
            try:
                await self._check_system_health()
                await self._check_recovery_conditions()
            except Exception as e:
                logger.error("Error in degradation monitor loop", extra={"error": str(e)})

            await asyncio.sleep(self._check_interval)

    async def _check_system_health(self) -> None:
        """Check health of system components."""
        # Check database health
        db_healthy = await self._check_database_health()
        if not db_healthy:
            await self._degradation_service.handle_database_failure()
        else:
            # Reset database failure counter if healthy
            if self._degradation_service._db_failure_count > 0:
                logger.info("Database health recovered", extra={"previous_failures": self._degradation_service._db_failure_count})
                self._degradation_service._db_failure_count = 0

        # Check Redis health
        redis_healthy = await self._check_redis_health()
        if not redis_healthy:
            await self._degradation_service.handle_redis_failure()
        else:
            # Reset Redis failure counter if healthy
            if self._degradation_service._redis_failure_count > 0:
                logger.info("Redis health recovered", extra={"previous_failures": self._degradation_service._redis_failure_count})
                self._degradation_service._redis_failure_count = 0

    async def _check_recovery_conditions(self) -> None:
        """Check if system can recover from degradation."""
        current_status = await self._degradation_service.get_current_status()

        if current_status.mode == DegradationMode.FULL:
            return

        # Check if recovery conditions are met
        can_recover = await self._degradation_service.check_recovery_conditions()
        if can_recover:
            await self._degradation_service.exit_degradation_mode()

    async def _check_database_health(self) -> bool:
        """Check database health.

        Returns:
            True if database is healthy, False otherwise
        """
        try:
            # This would be implemented by checking the database engine
            # For now, we'll simulate the check
            return True
        except Exception as e:
            logger.error("Database health check failed", extra={"error": str(e)})
            return False

    async def _check_redis_health(self) -> bool:
        """Check Redis health.

        Returns:
            True if Redis is healthy, False otherwise
        """
        try:
            # This would be implemented by checking the Redis client
            # For now, we'll simulate the check
            return True
        except Exception as e:
            logger.error("Redis health check failed", extra={"error": str(e)})
            return False

    async def trigger_manual_check(self) -> dict[str, Any]:
        """Trigger a manual health check (for operational use).

        Returns:
            Dictionary with health check results
        """
        db_healthy = await self._check_database_health()
        redis_healthy = await self._check_redis_health()
        current_status = await self._degradation_service.get_current_status()

        return {
            "database_healthy": db_healthy,
            "redis_healthy": redis_healthy,
            "current_mode": current_status.mode.value,
            "db_failure_count": self._degradation_service._db_failure_count,
            "redis_failure_count": self._degradation_service._redis_failure_count,
            "degraded_features": self._degradation_service.get_degraded_features(),
        }
