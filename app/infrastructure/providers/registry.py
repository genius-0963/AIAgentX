"""Provider registry for managing provider instances."""

from __future__ import annotations

from typing import Any

from app.domain.providers.protocols import ModelProvider
from app.domain.providers.value_objects import ProviderConfig, RetryPolicy, CircuitBreakerConfig
from app.infrastructure.observability.logging import get_logger

logger = get_logger(__name__)


class ProviderRegistry:
    """Registry for managing provider instances.

    The provider registry is responsible for:
    - Registering provider instances
    - Retrieving providers by name
    - Provider factory pattern for instantiation
    - Configuration validation
    """

    def __init__(self) -> None:
        self._providers: dict[str, ModelProvider] = {}
        self._configs: dict[str, ProviderConfig] = {}
        self._retry_policies: dict[str, RetryPolicy] = {}
        self._circuit_breaker_configs: dict[str, CircuitBreakerConfig] = {}

    def register_provider(
        self,
        provider: ModelProvider,
        config: ProviderConfig,
        retry_policy: RetryPolicy | None = None,
        circuit_breaker_config: CircuitBreakerConfig | None = None,
    ) -> None:
        """Register a provider instance.

        Args:
            provider: The provider instance to register
            config: Provider configuration
            retry_policy: Optional retry policy
            circuit_breaker_config: Optional circuit breaker configuration
        """
        provider_name = provider.provider_name

        if provider_name in self._providers:
            logger.warning(
                "Provider already registered, overwriting",
                extra={"provider": provider_name},
            )

        self._providers[provider_name] = provider
        self._configs[provider_name] = config

        if retry_policy:
            self._retry_policies[provider_name] = retry_policy
        if circuit_breaker_config:
            self._circuit_breaker_configs[provider_name] = circuit_breaker_config

        logger.info(
            "Provider registered",
            extra={
                "provider": provider_name,
                "model": config.model,
                "has_retry_policy": retry_policy is not None,
                "has_circuit_breaker": circuit_breaker_config is not None,
            },
        )

    def get_provider(self, provider_name: str) -> ModelProvider | None:
        """Get a provider by name.

        Args:
            provider_name: Name of the provider to retrieve

        Returns:
            ModelProvider if found, None otherwise
        """
        return self._providers.get(provider_name)

    def get_provider_config(self, provider_name: str) -> ProviderConfig | None:
        """Get provider configuration.

        Args:
            provider_name: Name of the provider

        Returns:
            ProviderConfig if found, None otherwise
        """
        return self._configs.get(provider_name)

    def get_retry_policy(self, provider_name: str) -> RetryPolicy | None:
        """Get retry policy for a provider.

        Args:
            provider_name: Name of the provider

        Returns:
            RetryPolicy if found, None otherwise
        """
        return self._retry_policies.get(provider_name)

    def get_circuit_breaker_config(self, provider_name: str) -> CircuitBreakerConfig | None:
        """Get circuit breaker configuration for a provider.

        Args:
            provider_name: Name of the provider

        Returns:
            CircuitBreakerConfig if found, None otherwise
        """
        return self._circuit_breaker_configs.get(provider_name)

    def list_providers(self) -> list[str]:
        """List all registered provider names.

        Returns:
            List of provider names
        """
        return list(self._providers.keys())

    def unregister_provider(self, provider_name: str) -> None:
        """Unregister a provider.

        Args:
            provider_name: Name of the provider to unregister
        """
        if provider_name in self._providers:
            del self._providers[provider_name]
            del self._configs[provider_name]
            self._retry_policies.pop(provider_name, None)
            self._circuit_breaker_configs.pop(provider_name, None)

            logger.info("Provider unregistered", extra={"provider": provider_name})

    def clear_all(self) -> None:
        """Clear all registered providers."""
        self._providers.clear()
        self._configs.clear()
        self._retry_policies.clear()
        self._circuit_breaker_configs.clear()
        logger.info("All providers cleared from registry")

    def validate_config(self, config: ProviderConfig) -> bool:
        """Validate provider configuration.

        Args:
            config: Provider configuration to validate

        Returns:
            True if configuration is valid, False otherwise
        """
        try:
            # ProviderConfig has __post_init__ validation
            _ = ProviderConfig(**config.__dict__)  # type: ignore[arg-type]
            return True
        except Exception as e:
            logger.error(
                "Provider configuration validation failed",
                extra={
                    "provider": config.provider,
                    "error": str(e),
                },
            )
            return False

    def get_registry_status(self) -> dict[str, Any]:
        """Get registry status for monitoring.

        Returns:
            Dictionary with registry status information
        """
        return {
            "total_providers": len(self._providers),
            "providers": [
                {
                    "name": name,
                    "model": self._configs[name].model if name in self._configs else None,
                    "has_retry_policy": name in self._retry_policies,
                    "has_circuit_breaker": name in self._circuit_breaker_configs,
                }
                for name in self._providers.keys()
            ],
        }
