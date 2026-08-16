"""Retry logic with exponential backoff and error classification."""

from __future__ import annotations

import random
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any

import httpx

from app.domain.providers.models import ProviderError
from app.domain.providers.value_objects import RetryPolicy
from app.infrastructure.observability.logging import get_logger

logger = get_logger(__name__)


class ErrorType(Enum):
    """Classification of error types for retry logic."""

    TIMEOUT = "timeout"
    RATE_LIMIT = "rate_limit"
    SERVER_ERROR = "server_error"
    AUTH_ERROR = "auth_error"
    VALIDATION_ERROR = "validation_error"
    NETWORK_ERROR = "network_error"
    UNKNOWN = "unknown"


@dataclass(slots=True, kw_only=True)
class RetryContext:
    """Context for tracking retry attempts."""

    attempt: int
    total_delay_ms: float
    last_error: Exception
    is_last_attempt: bool

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for logging."""
        return {
            "attempt": self.attempt,
            "total_delay_ms": self.total_delay_ms,
            "error_type": type(self.last_error).__name__,
            "error_message": str(self.last_error),
            "is_last_attempt": self.is_last_attempt,
        }


def classify_error(error: Exception) -> ProviderError:
    """Classify an error as retryable or non-retryable.

    Args:
        error: The exception to classify

    Returns:
        ProviderError with classification
    """
    if isinstance(error, httpx.TimeoutException):
        return ProviderError(
            is_retryable=True,
            error_type=ErrorType.TIMEOUT.value,
            original_error=error,
            provider="",
            message="Request timed out",
        )
    elif isinstance(error, httpx.HTTPStatusError):
        status_code = error.response.status_code
        if status_code == 429:
            retry_after = error.response.headers.get("Retry-After")
            retry_after_seconds = int(retry_after) if retry_after else None
            return ProviderError(
                is_retryable=True,
                error_type=ErrorType.RATE_LIMIT.value,
                original_error=error,
                provider="",
                message="Rate limit exceeded",
            )
        elif 500 <= status_code < 600:
            return ProviderError(
                is_retryable=True,
                error_type=ErrorType.SERVER_ERROR.value,
                original_error=error,
                provider="",
                message=f"Server error: {status_code}",
            )
        elif status_code == 401:
            return ProviderError(
                is_retryable=False,
                error_type=ErrorType.AUTH_ERROR.value,
                original_error=error,
                provider="",
                message="Authentication failed",
            )
        elif status_code == 400:
            return ProviderError(
                is_retryable=False,
                error_type=ErrorType.VALIDATION_ERROR.value,
                original_error=error,
                provider="",
                message="Request validation failed",
            )
        else:
            return ProviderError(
                is_retryable=False,
                error_type=ErrorType.UNKNOWN.value,
                original_error=error,
                provider="",
                message=f"HTTP error: {status_code}",
            )
    elif isinstance(error, (httpx.ConnectError, httpx.ConnectTimeout)):
        return ProviderError(
            is_retryable=True,
            error_type=ErrorType.NETWORK_ERROR.value,
            original_error=error,
            provider="",
            message="Connection failed",
        )
    else:
        return ProviderError(
            is_retryable=False,
            error_type=ErrorType.UNKNOWN.value,
            original_error=error,
            provider="",
            message=str(error),
        )


def calculate_backoff(attempt: int, policy: RetryPolicy) -> float:
    """Calculate exponential backoff with jitter.

    Args:
        attempt: Current retry attempt (0-based)
        policy: Retry policy configuration

    Returns:
        Backoff time in milliseconds
    """
    base_backoff = policy.initial_backoff_ms * (policy.backoff_multiplier ** attempt)
    capped_backoff = min(base_backoff, policy.max_backoff_ms)

    if policy.jitter:
        # Full jitter: random value between 0 and capped_backoff
        return random.uniform(0, capped_backoff)
    return capped_backoff


class RetryHandler:
    """Handler for retry logic with backoff and budget enforcement."""

    def __init__(self, policy: RetryPolicy) -> None:
        self._policy = policy

    async def execute_with_retry(
        self,
        func,
        *args: Any,
        provider_name: str = "",
        **kwargs: Any,
    ) -> Any:
        """Execute a function with retry logic.

        Args:
            func: The async function to execute
            *args: Positional arguments for the function
            provider_name: Provider name for logging
            **kwargs: Keyword arguments for the function

        Returns:
            The result of the function call

        Raises:
            The last exception if all retries are exhausted
        """
        last_error: Exception | None = None
        total_delay_ms = 0.0

        for attempt in range(self._policy.max_retries + 1):
            try:
                return await func(*args, **kwargs)

            except Exception as e:
                last_error = e
                provider_error = classify_error(e)
                provider_error.provider = provider_name

                context = RetryContext(
                    attempt=attempt,
                    total_delay_ms=total_delay_ms,
                    last_error=e,
                    is_last_attempt=attempt >= self._policy.max_retries,
                )

                if not provider_error.is_retryable or context.is_last_attempt:
                    logger.error(
                        "Function execution failed permanently",
                        extra={
                            "provider": provider_name,
                            **context.to_dict(),
                            "error_type": provider_error.error_type,
                        },
                    )
                    raise

                # Calculate backoff and wait
                backoff_ms = calculate_backoff(attempt, self._policy)
                total_delay_ms += backoff_ms

                logger.warning(
                    "Function execution failed, retrying",
                    extra={
                        "provider": provider_name,
                        **context.to_dict(),
                        "backoff_ms": backoff_ms,
                        "error_type": provider_error.error_type,
                    },
                )

                await self._sleep(backoff_ms / 1000)

        # This should never be reached, but just in case
        if last_error:
            raise last_error
        raise RuntimeError("Max retries exceeded without exception")

    async def _sleep(self, seconds: float) -> None:
        """Async sleep helper."""
        import asyncio

        await asyncio.sleep(seconds)
