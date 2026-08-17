"""Fallback mechanism for provider resilience."""

from __future__ import annotations

import time
from dataclasses import dataclass
from enum import Enum
from typing import Any

from app.domain.providers.value_objects import FallbackConfig
from app.infrastructure.observability.logging import get_logger

logger = get_logger(__name__)


class FallbackReason(Enum):
    """Reasons for triggering fallback."""

    CIRCUIT_OPEN = "circuit_open"
    TIMEOUT = "timeout"
    RATE_LIMIT = "rate_limit"
    SERVER_ERROR = "server_error"
    AUTH_ERROR = "auth_error"
    MANUAL = "manual"


@dataclass(slots=True, kw_only=True)
class FallbackDecision:
    """Decision about whether to fallback and to which provider."""

    should_fallback: bool
    target_provider: str | None = None
    reason: FallbackReason = FallbackReason.MANUAL
    metadata: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for logging."""
        return {
            "should_fallback": self.should_fallback,
            "target_provider": self.target_provider,
            "reason": self.reason.value,
            "metadata": self.metadata or {},
        }


class FallbackHandler:
    """Handler for fallback logic between providers.

    The fallback handler determines when and how to fallback from a primary
    provider to a fallback provider based on circuit breaker state, error types,
    and configuration rules.
    """

    def __init__(self, config: FallbackConfig) -> None:
        self._config = config
        self._fallback_count: dict[str, int] = {}

    def should_fallback(
        self,
        primary_provider: str,
        error_type: str,
        circuit_state: str,
        irreversible_effects_executed: bool = False,
    ) -> FallbackDecision:
        """Determine if fallback should occur.

        Args:
            primary_provider: The primary provider that failed
            error_type: Type of error that occurred
            circuit_state: Current circuit breaker state
            irreversible_effects_executed: Whether irreversible effects have been executed

        Returns:
            FallbackDecision with fallback recommendation
        """
        # Don't fallback if irreversible effects have been executed
        if irreversible_effects_executed:
            logger.warning(
                "Fallback skipped due to irreversible effects",
                extra={
                    "primary_provider": primary_provider,
                    "error_type": error_type,
                },
            )
            return FallbackDecision(
                should_fallback=False,
                reason=FallbackReason.MANUAL,
                metadata={"reason": "irreversible_effects_executed"},
            )

        # Check if fallback is allowed based on error type
        if not self._is_error_type_fallbackable(error_type):
            return FallbackDecision(
                should_fallback=False,
                reason=FallbackReason.MANUAL,
                metadata={"reason": "error_type_not_fallbackable"},
            )

        # Check if circuit breaker is open
        if circuit_state == "open":
            return self._create_fallback_decision(
                primary_provider, FallbackReason.CIRCUIT_OPEN, {"circuit_state": circuit_state}
            )

        # Check for specific error types that trigger fallback
        if error_type == "timeout":
            return self._create_fallback_decision(
                primary_provider, FallbackReason.TIMEOUT, {"error_type": error_type}
            )
        elif error_type == "rate_limit":
            return self._create_fallback_decision(
                primary_provider, FallbackReason.RATE_LIMIT, {"error_type": error_type}
            )
        elif error_type == "server_error":
            return self._create_fallback_decision(
                primary_provider, FallbackReason.SERVER_ERROR, {"error_type": error_type}
            )

        # Don't fallback for other error types
        return FallbackDecision(
            should_fallback=False,
            reason=FallbackReason.MANUAL,
            metadata={"reason": "error_type_not_fallbackable"},
        )

    def get_fallback_provider(self, primary_provider: str) -> str | None:
        """Get the next fallback provider.

        Args:
            primary_provider: The primary provider that failed

        Returns:
            Name of fallback provider or None if no fallback available
        """
        if not self._config.fallback_providers:
            return None

        # Get fallback count for primary provider
        fallback_count = self._fallback_count.get(primary_provider, 0)

        # Check if we've exceeded max fallback attempts
        if fallback_count >= self._config.max_fallback_attempts:
            logger.warning(
                "Max fallback attempts exceeded",
                extra={
                    "primary_provider": primary_provider,
                    "fallback_count": fallback_count,
                    "max_attempts": self._config.max_fallback_attempts,
                },
            )
            return None

        # Get next fallback provider in sequence
        fallback_index = fallback_count % len(self._config.fallback_providers)
        fallback_provider = self._config.fallback_providers[fallback_index]

        # Increment fallback count
        self._fallback_count[primary_provider] = fallback_count + 1

        logger.info(
            "Fallback provider selected",
            extra={
                "primary_provider": primary_provider,
                "fallback_provider": fallback_provider,
                "fallback_count": fallback_count + 1,
            },
        )

        return fallback_provider

    def validate_provider_compatibility(
        self, primary_provider: str, fallback_provider: str
    ) -> bool:
        """Validate that fallback provider is compatible with primary.

        Args:
            primary_provider: The primary provider
            fallback_provider: The fallback provider to validate

        Returns:
            True if providers are compatible, False otherwise
        """
        # In a real implementation, this would check:
        # - Data residency requirements
        # - Capability class matching
        # - Model compatibility
        # - Feature parity

        # For now, simple validation
        if primary_provider == fallback_provider:
            logger.warning(
                "Fallback provider same as primary",
                extra={"provider": primary_provider},
            )
            return False

        # Check if fallback provider is in configured list
        if fallback_provider not in self._config.fallback_providers:
            logger.warning(
                "Fallback provider not in configured list",
                extra={
                    "fallback_provider": fallback_provider,
                    "configured_providers": self._config.fallback_providers,
                },
            )
            return False

        return True

    def record_fallback_success(self, primary_provider: str, fallback_provider: str) -> None:
        """Record a successful fallback.

        Args:
            primary_provider: The primary provider that failed
            fallback_provider: The fallback provider that succeeded
        """
        logger.info(
            "Fallback successful",
            extra={
                "primary_provider": primary_provider,
                "fallback_provider": fallback_provider,
            },
        )

    def record_fallback_failure(self, primary_provider: str, fallback_provider: str, error: str) -> None:
        """Record a failed fallback attempt.

        Args:
            primary_provider: The primary provider that failed
            fallback_provider: The fallback provider that also failed
            error: Error message from the fallback attempt
        """
        logger.error(
            "Fallback failed",
            extra={
                "primary_provider": primary_provider,
                "fallback_provider": fallback_provider,
                "error": error,
            },
        )

    def reset_fallback_count(self, primary_provider: str) -> None:
        """Reset fallback count for a provider.

        Args:
            primary_provider: The primary provider to reset
        """
        if primary_provider in self._fallback_count:
            del self._fallback_count[primary_provider]
            logger.info("Fallback count reset", extra={"primary_provider": primary_provider})

    def reset_all_fallback_counts(self) -> None:
        """Reset all fallback counts."""
        self._fallback_count.clear()
        logger.info("All fallback counts reset")

    def _is_error_type_fallbackable(self, error_type: str) -> bool:
        """Check if error type is suitable for fallback.

        Args:
            error_type: The error type to check

        Returns:
            True if error type is fallbackable, False otherwise
        """
        fallbackable_types = {"timeout", "rate_limit", "server_error"}
        return error_type in fallbackable_types

    def _create_fallback_decision(
        self, primary_provider: str, reason: FallbackReason, metadata: dict[str, Any]
    ) -> FallbackDecision:
        """Create a fallback decision.

        Args:
            primary_provider: The primary provider
            reason: The reason for fallback
            metadata: Additional metadata

        Returns:
            FallbackDecision with fallback recommendation
        """
        fallback_provider = self.get_fallback_provider(primary_provider)

        if fallback_provider and self.validate_provider_compatibility(primary_provider, fallback_provider):
            return FallbackDecision(
                should_fallback=True,
                target_provider=fallback_provider,
                reason=reason,
                metadata=metadata,
            )

        return FallbackDecision(
            should_fallback=False,
            reason=reason,
            metadata={**metadata, "reason": "no_valid_fallback_provider"},
        )
