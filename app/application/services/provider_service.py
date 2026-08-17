"""Provider orchestration service."""

from __future__ import annotations

from typing import Any

from app.domain.providers.models import ModelRequest, ModelResponse, ProviderError
from app.domain.providers.protocols import ModelProvider
from app.domain.providers.value_objects import (
    ProviderConfig,
    RetryPolicy,
    CircuitBreakerConfig,
    FallbackConfig,
)
from app.infrastructure.providers.circuit_breaker import CircuitBreaker
from app.infrastructure.providers.fallback import FallbackHandler
from app.infrastructure.providers.health import ProviderHealthMonitor
from app.infrastructure.providers.registry import ProviderRegistry
from app.infrastructure.observability.logging import get_logger

logger = get_logger(__name__)


class ProviderService:
    """Service for orchestrating provider calls with resilience features.

    This service provides a unified interface for making provider calls with:
    - Provider selection based on model policy
    - Retry logic with exponential backoff
    - Circuit breaking for fault tolerance
    - Fallback mechanism for high availability
    - Request/response normalization
    - Usage tracking integration
    """

    def __init__(
        self,
        registry: ProviderRegistry,
        health_monitor: ProviderHealthMonitor,
        cost_service: Any,  # CostService
        fallback_config: FallbackConfig | None = None,
    ) -> None:
        self._registry = registry
        self._health_monitor = health_monitor
        self._cost_service = cost_service
        self._fallback_config = fallback_config or FallbackConfig(primary_provider="openai")
        self._fallback_handler = FallbackHandler(self._fallback_config)
        self._circuit_breakers: dict[str, CircuitBreaker] = {}

    def register_provider(
        self,
        provider: ModelProvider,
        config: ProviderConfig,
        retry_policy: RetryPolicy | None = None,
        circuit_breaker_config: CircuitBreakerConfig | None = None,
    ) -> None:
        """Register a provider with the service.

        Args:
            provider: The provider instance
            config: Provider configuration
            retry_policy: Optional retry policy
            circuit_breaker_config: Optional circuit breaker configuration
        """
        # Register with registry
        self._registry.register_provider(provider, config, retry_policy, circuit_breaker_config)

        # Register with health monitor
        self._health_monitor.register_provider(provider.provider_name)

        # Create circuit breaker if config provided
        if circuit_breaker_config:
            circuit_breaker = CircuitBreaker(
                config=circuit_breaker_config,
                provider_name=provider.provider_name,
            )
            self._circuit_breakers[provider.provider_name] = circuit_breaker

        logger.info(
            "Provider registered with service",
            extra={"provider": provider.provider_name},
        )

    async def complete(
        self,
        request: ModelRequest,
        provider_name: str | None = None,
        enable_fallback: bool = True,
    ) -> ModelResponse:
        """Execute a model completion with resilience features.

        Args:
            request: The model request
            provider_name: Optional specific provider to use
            enable_fallback: Whether to enable fallback mechanism

        Returns:
            ModelResponse from the provider

        Raises:
            ProviderUnavailableError: If all providers are unavailable
        """
        # Select provider
        if provider_name:
            provider = self._registry.get_provider(provider_name)
            if not provider:
                raise ValueError(f"Provider {provider_name} not found")
        else:
            provider = self._select_provider(request)
            if not provider:
                raise ValueError("No provider available")

        provider_name = provider.provider_name

        # Check circuit breaker
        circuit_breaker = self._circuit_breakers.get(provider_name)
        if circuit_breaker and not circuit_breaker.can_execute():
            logger.warning(
                "Circuit breaker open, attempting fallback",
                extra={"provider": provider_name},
            )
            if enable_fallback:
                return await self._attempt_fallback(request, provider_name, "circuit_open")
            else:
                from app.domain.providers.exceptions import ProviderUnavailableError

                raise ProviderUnavailableError(
                    f"Circuit breaker open for provider {provider_name}", provider_name
                )

        # Execute request with circuit breaker tracking
        try:
            response = await self._execute_with_circuit_breaker(provider, request, circuit_breaker)

            # Record success
            if circuit_breaker:
                circuit_breaker.record_success()

            # Record health check
            self._health_monitor.record_health_check(
                provider_name, is_healthy=True, latency_ms=response.latency_ms
            )

            return response

        except Exception as e:
            # Record failure
            if circuit_breaker:
                circuit_breaker.record_failure()

            # Record health check
            self._health_monitor.record_health_check(provider_name, is_healthy=False, latency_ms=0)

            # Attempt fallback if enabled
            if enable_fallback:
                error_type = self._classify_error(e)
                circuit_state = circuit_breaker.state.value if circuit_breaker else "closed"

                fallback_decision = self._fallback_handler.should_fallback(
                    primary_provider=provider_name,
                    error_type=error_type,
                    circuit_state=circuit_state,
                )

                if fallback_decision.should_fallback:
                    return await self._attempt_fallback(
                        request, provider_name, fallback_decision.reason.value
                    )

            # Re-raise exception if no fallback
            raise

    def _select_provider(self, request: ModelRequest) -> ModelProvider | None:
        """Select a provider based on request and configuration.

        Args:
            request: The model request

        Returns:
            Selected provider or None
        """
        # Simple selection logic - use primary provider from config
        # In a real implementation, this would be more sophisticated
        provider_name = self._fallback_config.primary_provider
        return self._registry.get_provider(provider_name)

    async def _execute_with_circuit_breaker(
        self,
        provider: ModelProvider,
        request: ModelRequest,
        circuit_breaker: CircuitBreaker | None,
    ) -> ModelResponse:
        """Execute request with circuit breaker tracking.

        Args:
            provider: The provider to use
            request: The model request
            circuit_breaker: Optional circuit breaker

        Returns:
            ModelResponse from the provider
        """
        # The provider's complete method already handles retry logic
        return await provider.complete(request)

    async def _attempt_fallback(
        self, request: ModelRequest, primary_provider: str, reason: str
    ) -> ModelResponse:
        """Attempt fallback to alternative provider.

        Args:
            request: The model request
            primary_provider: The primary provider that failed
            reason: Reason for fallback

        Returns:
            ModelResponse from fallback provider

        Raises:
            ProviderUnavailableError: If fallback fails
        """
        fallback_provider_name = self._fallback_handler.get_fallback_provider(primary_provider)

        if not fallback_provider_name:
            from app.domain.providers.exceptions import ProviderUnavailableError

            raise ProviderUnavailableError(
                f"No fallback provider available for {primary_provider}", primary_provider
            )

        # Validate compatibility
        if not self._fallback_handler.validate_provider_compatibility(
            primary_provider, fallback_provider_name
        ):
            from app.domain.providers.exceptions import ProviderUnavailableError

            raise ProviderUnavailableError(
                f"Fallback provider {fallback_provider_name} not compatible with {primary_provider}",
                primary_provider,
            )

        fallback_provider = self._registry.get_provider(fallback_provider_name)
        if not fallback_provider:
            from app.domain.providers.exceptions import ProviderUnavailableError

            raise ProviderUnavailableError(
                f"Fallback provider {fallback_provider_name} not found", primary_provider
            )

        try:
            logger.info(
                "Attempting fallback",
                extra={
                    "primary_provider": primary_provider,
                    "fallback_provider": fallback_provider_name,
                    "reason": reason,
                },
            )

            response = await fallback_provider.complete(request)

            self._fallback_handler.record_fallback_success(primary_provider, fallback_provider_name)

            return response

        except Exception as e:
            self._fallback_handler.record_fallback_failure(
                primary_provider, fallback_provider_name, str(e)
            )
            raise

    def _classify_error(self, error: Exception) -> str:
        """Classify error for fallback decision.

        Args:
            error: The exception to classify

        Returns:
            Error type string
        """
        from app.domain.providers.exceptions import (
            ProviderTimeoutError,
            ProviderRateLimitError,
            ProviderAuthenticationError,
            ProviderValidationError,
        )

        if isinstance(error, ProviderTimeoutError):
            return "timeout"
        elif isinstance(error, ProviderRateLimitError):
            return "rate_limit"
        elif isinstance(error, ProviderAuthenticationError):
            return "auth_error"
        elif isinstance(error, ProviderValidationError):
            return "validation_error"
        else:
            return "server_error"

    def get_provider_health(self, provider_name: str) -> dict[str, Any] | None:
        """Get health status for a provider.

        Args:
            provider_name: Name of the provider

        Returns:
            Health status dictionary or None
        """
        health = self._health_monitor.get_provider_health(provider_name)
        if health:
            return health.to_dict()
        return None

    def get_circuit_breaker_status(self, provider_name: str) -> dict[str, Any] | None:
        """Get circuit breaker status for a provider.

        Args:
            provider_name: Name of the provider

        Returns:
            Circuit breaker status dictionary or None
        """
        circuit_breaker = self._circuit_breakers.get(provider_name)
        if circuit_breaker:
            return circuit_breaker.get_status()
        return None

    def reset_circuit_breaker(self, provider_name: str) -> bool:
        """Reset circuit breaker for a provider.

        Args:
            provider_name: Name of the provider

        Returns:
            True if reset was successful, False otherwise
        """
        circuit_breaker = self._circuit_breakers.get(provider_name)
        if circuit_breaker:
            circuit_breaker.reset()
            return True
        return False

    def get_service_status(self) -> dict[str, Any]:
        """Get overall service status.

        Returns:
            Dictionary with service status information
        """
        return {
            "registry_status": self._registry.get_registry_status(),
            "health_status": self._health_monitor.get_overall_health(),
            "circuit_breakers": {
                name: cb.get_status() for name, cb in self._circuit_breakers.items()
            },
            "fallback_config": {
                "primary_provider": self._fallback_config.primary_provider,
                "fallback_providers": self._fallback_config.fallback_providers,
                "max_fallback_attempts": self._fallback_config.max_fallback_attempts,
            },
        }
