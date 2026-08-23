"""Graceful degradation service for handling partial failures."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING

from app.infrastructure.observability.logging import get_logger

if TYPE_CHECKING:
    from app.settings import Settings

logger = get_logger(__name__)


class DegradationMode(StrEnum):
    """System degradation modes."""

    FULL = "full"
    DEGRADED_CACHE = "degraded_cache"
    DEGRADED_DB = "degraded_db"
    DEGRADED_PROVIDERS = "degraded_providers"
    MINIMAL = "minimal"


@dataclass(frozen=True, slots=True)
class DegradationStatus:
    """Current degradation status."""

    mode: DegradationMode
    reason: str | None = None
    affected_components: list[str] | None = None
    entered_at: datetime | None = None
    auto_recovery_enabled: bool = True


class DegradationService:
    """Service for managing graceful degradation under partial failures."""

    def __init__(
        self,
        settings: Settings,
        database_failure_threshold: int = 5,
        redis_failure_threshold: int = 3,
    ) -> None:
        """Initialize degradation service.

        Args:
            settings: Application settings
            database_failure_threshold: Number of consecutive DB failures before degradation
            redis_failure_threshold: Number of consecutive Redis failures before degradation
        """
        self._settings = settings
        self._db_failure_threshold = database_failure_threshold
        self._redis_failure_threshold = redis_failure_threshold

        self._current_status = DegradationStatus(
            mode=DegradationMode.FULL,
            entered_at=datetime.now(UTC),
        )

        self._db_failure_count = 0
        self._redis_failure_count = 0
        self._provider_failures: dict[str, int] = {}

    async def handle_database_failure(self) -> DegradationStatus:
        """Handle database failure and potentially enter degradation mode.

        Returns:
            Current degradation status
        """
        self._db_failure_count += 1

        logger.warning(
            "Database failure detected",
            extra={
                "failure_count": self._db_failure_count,
                "threshold": self._db_failure_threshold,
            },
        )

        if self._db_failure_count >= self._db_failure_threshold:
            return await self._enter_degradation_mode(
                DegradationMode.DEGRADED_DB,
                reason=f"Database failure threshold exceeded ({self._db_failure_count} failures)",
                affected_components=["database"],
            )

        return self._current_status

    async def handle_redis_failure(self) -> DegradationStatus:
        """Handle Redis failure and potentially enter degradation mode.

        Returns:
            Current degradation status
        """
        self._redis_failure_count += 1

        logger.warning(
            "Redis failure detected",
            extra={
                "failure_count": self._redis_failure_count,
                "threshold": self._redis_failure_threshold,
            },
        )

        if self._redis_failure_count >= self._redis_failure_threshold:
            return await self._enter_degradation_mode(
                DegradationMode.DEGRADED_CACHE,
                reason=f"Redis failure threshold exceeded ({self._redis_failure_count} failures)",
                affected_components=["cache", "rate_limiting", "idempotency"],
            )

        return self._current_status

    async def handle_provider_failure(self, provider: str) -> DegradationStatus:
        """Handle provider failure and potentially enter degradation mode.

        Args:
            provider: Provider name that failed

        Returns:
            Current degradation status
        """
        self._provider_failures[provider] = self._provider_failures.get(provider, 0) + 1

        logger.warning(
            "Provider failure detected",
            extra={"provider": provider, "failure_count": self._provider_failures[provider]},
        )

        # Provider failures are handled differently - may trigger fallback rather than degradation
        # For now, we'll just log and return current status
        return self._current_status

    async def _enter_degradation_mode(
        self,
        mode: DegradationMode,
        reason: str,
        affected_components: list[str] | None = None,
    ) -> DegradationStatus:
        """Enter a degradation mode.

        Args:
            mode: Degradation mode to enter
            reason: Reason for degradation
            affected_components: List of affected components

        Returns:
            New degradation status
        """
        self._current_status = DegradationStatus(
            mode=mode,
            reason=reason,
            affected_components=affected_components,
            entered_at=datetime.now(UTC),
            auto_recovery_enabled=self._settings.degradation_auto_recovery,
        )

        logger.error(
            "System entered degradation mode",
            extra={
                "mode": mode.value,
                "reason": reason,
                "affected_components": affected_components,
            },
        )

        # Emit degradation event (would go to event system in real implementation)
        return self._current_status

    async def check_recovery_conditions(self) -> bool:
        """Check if conditions are met to exit degradation mode.

        Returns:
            True if recovery conditions are met, False otherwise
        """
        if not self._current_status.auto_recovery_enabled:
            return False

        if self._current_status.mode == DegradationMode.FULL:
            return True

        # Check if the failed components have recovered
        if self._current_status.mode == DegradationMode.DEGRADED_DB:
            # Would check if database is now available
            return self._db_failure_count == 0

        if self._current_status.mode == DegradationMode.DEGRADED_CACHE:
            # Would check if Redis is now available
            return self._redis_failure_count == 0

        return False

    async def exit_degradation_mode(self) -> DegradationStatus:
        """Exit degradation mode and return to full operation.

        Returns:
            New degradation status
        """
        previous_mode = self._current_status.mode

        self._current_status = DegradationStatus(
            mode=DegradationMode.FULL,
            entered_at=datetime.now(UTC),
        )

        # Reset failure counters
        self._db_failure_count = 0
        self._redis_failure_count = 0
        self._provider_failures.clear()

        logger.info(
            "System exited degradation mode",
            extra={"previous_mode": previous_mode.value},
        )

        return self._current_status

    async def get_current_status(self) -> DegradationStatus:
        """Get current degradation status.

        Returns:
            Current degradation status
        """
        return self._current_status

    def get_degraded_features(self) -> list[str]:
        """Get list of features that are currently degraded.

        Returns:
            List of degraded feature names
        """
        if self._current_status.mode == DegradationMode.FULL:
            return []

        degraded_features = []

        if self._current_status.mode == DegradationMode.DEGRADED_CACHE:
            degraded_features.extend(["rate_limiting", "idempotency", "cancellation_pubsub"])

        if self._current_status.mode == DegradationMode.DEGRADED_DB:
            degraded_features.extend(["persistence", "audit_logging", "run_history"])

        if self._current_status.mode == DegradationMode.DEGRADED_PROVIDERS:
            degraded_features.extend(["provider_fallback", "advanced_features"])

        if self._current_status.mode == DegradationMode.MINIMAL:
            degraded_features.extend(
                ["rate_limiting", "idempotency", "persistence", "advanced_features"]
            )

        return degraded_features

    def is_feature_available(self, feature: str) -> bool:
        """Check if a feature is available in current degradation mode.

        Args:
            feature: Feature name to check

        Returns:
            True if feature is available, False otherwise
        """
        degraded_features = self.get_degraded_features()
        return feature not in degraded_features

    async def manual_degradation(self, mode: DegradationMode, reason: str) -> DegradationStatus:
        """Manually enter a degradation mode (for operational control).

        Args:
            mode: Degradation mode to enter
            reason: Reason for manual degradation

        Returns:
            New degradation status
        """
        return await self._enter_degradation_mode(
            mode,
            reason=f"Manual degradation: {reason}",
            affected_components=["manual"],
        )

    async def reset_failure_counters(self) -> None:
        """Reset all failure counters (for testing or recovery)."""
        self._db_failure_count = 0
        self._redis_failure_count = 0
        self._provider_failures.clear()

        logger.info("Failure counters reset")
