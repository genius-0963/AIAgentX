"""Fallback orchestration service."""

from __future__ import annotations

from typing import Any

from app.domain.providers.models import ModelRequest, ModelResponse
from app.domain.providers.protocols import ModelProvider
from app.domain.providers.value_objects import FallbackConfig
from app.infrastructure.providers.fallback import FallbackHandler, FallbackReason
from app.infrastructure.providers.registry import ProviderRegistry
from app.infrastructure.observability.logging import get_logger

logger = get_logger(__name__)


class FallbackService:
    """Service for managing fallback between providers.

    This service provides high-level fallback orchestration with:
    - Fallback decision logic
    - Provider compatibility validation
    - Fallback event logging
    - Fallback metrics tracking
    - Safety checks before fallback
    """

    def __init__(
        self,
        registry: ProviderRegistry,
        config: FallbackConfig,
    ) -> None:
        self._registry = registry
        self._config = config
        self._fallback_handler = FallbackHandler(config)
        self._fallback_metrics: dict[str, Any] = {
            "total_fallback_attempts": 0,
            "successful_fallbacks": 0,
            "failed_fallbacks": 0,
            "by_reason": {},
            "by_provider": {},
        }

    async def execute_with_fallback(
        self,
        request: ModelRequest,
        primary_provider_name: str,
        error_type: str,
        circuit_state: str,
        irreversible_effects_executed: bool = False,
    ) -> ModelResponse:
        """Execute request with fallback if primary provider fails.

        Args:
            request: The model request
            primary_provider_name: The primary provider that failed
            error_type: Type of error that occurred
            circuit_state: Current circuit breaker state
            irreversible_effects_executed: Whether irreversible effects have been executed

        Returns:
            ModelResponse from either primary or fallback provider

        Raises:
            ProviderUnavailableError: If fallback fails or is not allowed
        """
        # Check if fallback should occur
        fallback_decision = self._fallback_handler.should_fallback(
            primary_provider=primary_provider_name,
            error_type=error_type,
            circuit_state=circuit_state,
            irreversible_effects_executed=irreversible_effects_executed,
        )

        if not fallback_decision.should_fallback:
            from app.domain.providers.exceptions import ProviderUnavailableError

            raise ProviderUnavailableError(
                f"Fallback not allowed: {fallback_decision.metadata.get('reason', 'unknown')}",
                primary_provider_name,
            )

        # Increment fallback attempts
        self._fallback_metrics["total_fallback_attempts"] += 1

        # Get fallback provider
        fallback_provider_name = self._fallback_handler.get_fallback_provider(primary_provider_name)

        if not fallback_provider_name:
            self._record_fallback_failure(primary_provider_name, "no_fallback_provider")
            from app.domain.providers.exceptions import ProviderUnavailableError

            raise ProviderUnavailableError(
                "No fallback provider available", primary_provider_name
            )

        # Validate compatibility
        if not self._fallback_handler.validate_provider_compatibility(
            primary_provider_name, fallback_provider_name
        ):
            self._record_fallback_failure(primary_provider_name, "incompatible_provider")
            from app.domain.providers.exceptions import ProviderUnavailableError

            raise ProviderUnavailableError(
                f"Fallback provider {fallback_provider_name} not compatible",
                primary_provider_name,
            )

        # Get fallback provider instance
        fallback_provider = self._registry.get_provider(fallback_provider_name)
        if not fallback_provider:
            self._record_fallback_failure(primary_provider_name, "provider_not_found")
            from app.domain.providers.exceptions import ProviderUnavailableError

            raise ProviderUnavailableError(
                f"Fallback provider {fallback_provider_name} not found",
                primary_provider_name,
            )

        # Execute fallback request
        try:
            logger.info(
                "Executing fallback request",
                extra={
                    "primary_provider": primary_provider_name,
                    "fallback_provider": fallback_provider_name,
                    "error_type": error_type,
                    "circuit_state": circuit_state,
                },
            )

            response = await fallback_provider.complete(request)

            # Record successful fallback
            self._fallback_handler.record_fallback_success(
                primary_provider_name, fallback_provider_name
            )
            self._record_fallback_success(primary_provider_name, fallback_provider_name, fallback_decision.reason.value)

            return response

        except Exception as e:
            # Record failed fallback
            self._fallback_handler.record_fallback_failure(
                primary_provider_name, fallback_provider_name, str(e)
            )
            self._record_fallback_failure(primary_provider_name, str(e))

            logger.error(
                "Fallback request failed",
                extra={
                    "primary_provider": primary_provider_name,
                    "fallback_provider": fallback_provider_name,
                    "error": str(e),
                },
            )

            raise

    def can_fallback(
        self,
        primary_provider_name: str,
        error_type: str,
        circuit_state: str,
        irreversible_effects_executed: bool = False,
    ) -> bool:
        """Check if fallback is allowed.

        Args:
            primary_provider_name: The primary provider
            error_type: Type of error
            circuit_state: Circuit breaker state
            irreversible_effects_executed: Whether irreversible effects executed

        Returns:
            True if fallback is allowed, False otherwise
        """
        fallback_decision = self._fallback_handler.should_fallback(
            primary_provider=primary_provider_name,
            error_type=error_type,
            circuit_state=circuit_state,
            irreversible_effects_executed=irreversible_effects_executed,
        )

        return fallback_decision.should_fallback

    def get_fallback_provider(self, primary_provider_name: str) -> str | None:
        """Get the next fallback provider for a primary provider.

        Args:
            primary_provider_name: The primary provider name

        Returns:
            Fallback provider name or None
        """
        return self._fallback_handler.get_fallback_provider(primary_provider_name)

    def validate_provider_compatibility(
        self, primary_provider_name: str, fallback_provider_name: str
    ) -> bool:
        """Validate provider compatibility for fallback.

        Args:
            primary_provider_name: The primary provider
            fallback_provider_name: The fallback provider

        Returns:
            True if compatible, False otherwise
        """
        return self._fallback_handler.validate_provider_compatibility(
            primary_provider_name, fallback_provider_name
        )

    def reset_fallback_count(self, primary_provider_name: str) -> None:
        """Reset fallback count for a provider.

        Args:
            primary_provider_name: The primary provider to reset
        """
        self._fallback_handler.reset_fallback_count(primary_provider_name)

    def reset_all_fallback_counts(self) -> None:
        """Reset all fallback counts."""
        self._fallback_handler.reset_all_fallback_counts()

    def get_fallback_metrics(self) -> dict[str, Any]:
        """Get fallback metrics.

        Returns:
            Dictionary with fallback metrics
        """
        return self._fallback_metrics.copy()

    def _record_fallback_success(
        self, primary_provider: str, fallback_provider: str, reason: str
    ) -> None:
        """Record a successful fallback.

        Args:
            primary_provider: The primary provider
            fallback_provider: The fallback provider
            reason: The reason for fallback
        """
        self._fallback_metrics["successful_fallbacks"] += 1

        # Record by reason
        if reason not in self._fallback_metrics["by_reason"]:
            self._fallback_metrics["by_reason"][reason] = 0
        self._fallback_metrics["by_reason"][reason] += 1

        # Record by provider
        if primary_provider not in self._fallback_metrics["by_provider"]:
            self._fallback_metrics["by_provider"][primary_provider] = 0
        self._fallback_metrics["by_provider"][primary_provider] += 1

        logger.info(
            "Fallback successful",
            extra={
                "primary_provider": primary_provider,
                "fallback_provider": fallback_provider,
                "reason": reason,
            },
        )

    def _record_fallback_failure(self, primary_provider: str, error: str) -> None:
        """Record a failed fallback.

        Args:
            primary_provider: The primary provider
            error: The error message
        """
        self._fallback_metrics["failed_fallbacks"] += 1

        logger.error(
            "Fallback failed",
            extra={
                "primary_provider": primary_provider,
                "error": error,
            },
        )

    def update_config(self, config: FallbackConfig) -> None:
        """Update fallback configuration.

        Args:
            config: New fallback configuration
        """
        self._config = config
        self._fallback_handler = FallbackHandler(config)

        logger.info("Fallback configuration updated", extra={"config": str(config)})

    def get_config(self) -> FallbackConfig:
        """Get current fallback configuration.

        Returns:
            Current fallback configuration
        """
        return self._config
