"""Provider-specific exceptions."""

from __future__ import annotations


class ProviderError(Exception):
    """Base exception for provider errors."""

    def __init__(self, message: str, provider: str = "") -> None:
        self.provider = provider
        self.message = message
        super().__init__(f"[{provider}] {message}" if provider else message)


class ProviderUnavailableError(ProviderError):
    """Raised when provider is unavailable (circuit breaker open, network error, etc.)."""

    pass


class ProviderTimeoutError(ProviderError):
    """Raised when provider request times out."""

    pass


class ProviderRateLimitError(ProviderError):
    """Raised when provider rate limit is exceeded."""

    def __init__(self, message: str, provider: str = "", retry_after_seconds: int | None = None) -> None:
        self.retry_after_seconds = retry_after_seconds
        super().__init__(message, provider)


class ProviderAuthenticationError(ProviderError):
    """Raised when provider authentication fails."""

    pass


class ProviderValidationError(ProviderError):
    """Raised when provider request validation fails."""

    pass


class ProviderConfigurationError(ProviderError):
    """Raised when provider configuration is invalid."""

    pass
