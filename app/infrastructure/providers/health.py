"""Health monitoring for providers."""

from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from app.infrastructure.observability.logging import get_logger

logger = get_logger(__name__)


@dataclass(slots=True, kw_only=True)
class ProviderHealth:
    """Health status for a single provider."""

    provider_name: str
    is_healthy: bool = True
    last_check_time: float | None = None
    last_success_time: float | None = None
    last_failure_time: float | None = None
    consecutive_failures: int = 0
    consecutive_successes: int = 0
    total_checks: int = 0
    successful_checks: int = 0
    failed_checks: int = 0
    average_latency_ms: float = 0.0
    latency_samples: list[float] = field(default_factory=list)

    @property
    def success_rate(self) -> float:
        """Calculate success rate."""
        if self.total_checks == 0:
            return 1.0
        return self.successful_checks / self.total_checks

    def record_check(self, is_healthy: bool, latency_ms: float) -> None:
        """Record a health check result.

        Args:
            is_healthy: Whether the check was successful
            latency_ms: Latency of the health check in milliseconds
        """
        self.total_checks += 1
        self.last_check_time = time.time()

        if is_healthy:
            self.successful_checks += 1
            self.consecutive_successes += 1
            self.consecutive_failures = 0
            self.last_success_time = time.time()
            self.is_healthy = True
        else:
            self.failed_checks += 1
            self.consecutive_failures += 1
            self.consecutive_successes = 0
            self.last_failure_time = time.time()
            self.is_healthy = False

        # Update latency tracking
        self.latency_samples.append(latency_ms)
        if len(self.latency_samples) > 100:  # Keep last 100 samples
            self.latency_samples.pop(0)
        self.average_latency_ms = sum(self.latency_samples) / len(self.latency_samples)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for logging."""
        return {
            "provider_name": self.provider_name,
            "is_healthy": self.is_healthy,
            "last_check_time": self.last_check_time,
            "last_success_time": self.last_success_time,
            "last_failure_time": self.last_failure_time,
            "consecutive_failures": self.consecutive_failures,
            "consecutive_successes": self.consecutive_successes,
            "total_checks": self.total_checks,
            "successful_checks": self.successful_checks,
            "failed_checks": self.failed_checks,
            "success_rate": self.success_rate,
            "average_latency_ms": self.average_latency_ms,
        }


class ProviderHealthMonitor:
    """Monitor health status of multiple providers."""

    def __init__(self) -> None:
        self._providers: dict[str, ProviderHealth] = defaultdict(
            lambda: ProviderHealth(provider_name="")
        )

    def register_provider(self, provider_name: str) -> None:
        """Register a provider for health monitoring.

        Args:
            provider_name: Name of the provider to register
        """
        if provider_name not in self._providers:
            self._providers[provider_name] = ProviderHealth(provider_name=provider_name)
            logger.info("Provider registered for health monitoring", extra={"provider": provider_name})

    def record_health_check(self, provider_name: str, is_healthy: bool, latency_ms: float) -> None:
        """Record a health check result for a provider.

        Args:
            provider_name: Name of the provider
            is_healthy: Whether the check was successful
            latency_ms: Latency of the health check in milliseconds
        """
        if provider_name not in self._providers:
            self.register_provider(provider_name)

        self._providers[provider_name].record_check(is_healthy, latency_ms)

        logger.debug(
            "Health check recorded",
            extra={
                "provider": provider_name,
                "is_healthy": is_healthy,
                "latency_ms": latency_ms,
            },
        )

    def get_provider_health(self, provider_name: str) -> ProviderHealth | None:
        """Get health status for a specific provider.

        Args:
            provider_name: Name of the provider

        Returns:
            ProviderHealth if provider exists, None otherwise
        """
        return self._providers.get(provider_name)

    def is_provider_healthy(self, provider_name: str) -> bool:
        """Check if a provider is currently healthy.

        Args:
            provider_name: Name of the provider

        Returns:
            True if provider is healthy, False otherwise
        """
        health = self.get_provider_health(provider_name)
        return health.is_healthy if health else False

    def get_all_health_status(self) -> dict[str, dict[str, Any]]:
        """Get health status for all registered providers.

        Returns:
            Dictionary mapping provider names to health status dictionaries
        """
        return {name: health.to_dict() for name, health in self._providers.items()}

    def get_overall_health(self) -> dict[str, Any]:
        """Get overall health summary.

        Returns:
            Dictionary with overall health statistics
        """
        total_providers = len(self._providers)
        healthy_providers = sum(1 for health in self._providers.values() if health.is_healthy)

        return {
            "total_providers": total_providers,
            "healthy_providers": healthy_providers,
            "unhealthy_providers": total_providers - healthy_providers,
            "overall_healthy": healthy_providers == total_providers if total_providers > 0 else True,
            "provider_details": self.get_all_health_status(),
        }

    def reset_provider(self, provider_name: str) -> None:
        """Reset health tracking for a provider.

        Args:
            provider_name: Name of the provider to reset
        """
        if provider_name in self._providers:
            self._providers[provider_name] = ProviderHealth(provider_name=provider_name)
            logger.info("Provider health reset", extra={"provider": provider_name})

    def reset_all(self) -> None:
        """Reset health tracking for all providers."""
        self._providers.clear()
        logger.info("All provider health tracking reset")
