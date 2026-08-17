"""Circuit breaker implementation for provider resilience."""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from app.domain.providers.value_objects import CircuitBreakerConfig
from app.infrastructure.observability.logging import get_logger

logger = get_logger(__name__)


class CircuitState(Enum):
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation, requests pass through
    OPEN = "open"  # Circuit tripped, requests fail immediately
    HALF_OPEN = "half_open"  # Testing if provider has recovered


@dataclass(slots=True, kw_only=True)
class CircuitBreakerMetrics:
    """Metrics for circuit breaker monitoring."""

    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    last_failure_time: float | None = None
    last_success_time: float | None = None
    consecutive_failures: int = 0
    consecutive_successes: int = 0

    @property
    def failure_rate(self) -> float:
        """Calculate current failure rate."""
        if self.total_requests == 0:
            return 0.0
        return self.failed_requests / self.total_requests

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for logging."""
        return {
            "total_requests": self.total_requests,
            "successful_requests": self.successful_requests,
            "failed_requests": self.failed_requests,
            "failure_rate": self.failure_rate,
            "last_failure_time": self.last_failure_time,
            "last_success_time": self.last_success_time,
            "consecutive_failures": self.consecutive_failures,
            "consecutive_successes": self.consecutive_successes,
        }


@dataclass(slots=True, kw_only=True)
class CircuitBreaker:
    """Circuit breaker for provider resilience.

    The circuit breaker prevents cascade failures by tripping when a provider
    exhibits high failure rates. It implements three states:
    - CLOSED: Normal operation, requests pass through
    - OPEN: Circuit tripped, requests fail immediately
    - HALF_OPEN: Testing if provider has recovered with limited requests
    """

    config: CircuitBreakerConfig
    provider_name: str = ""
    _state: CircuitState = field(default_factory=lambda: CircuitState.CLOSED)
    _metrics: CircuitBreakerMetrics = field(default_factory=CircuitBreakerMetrics)
    _failure_window: deque[bool] = field(default_factory=lambda: deque(maxlen=100))  # True = success, False = failure
    _open_timestamp: float | None = None
    _half_open_calls: int = 0

    def __post_init__(self) -> None:
        if not self.provider_name:
            raise ValueError("Provider name cannot be empty")

    @property
    def state(self) -> CircuitState:
        """Get current circuit state."""
        return self._state

    @property
    def metrics(self) -> CircuitBreakerMetrics:
        """Get circuit breaker metrics."""
        return self._metrics

    def record_success(self) -> None:
        """Record a successful request."""
        self._metrics.total_requests += 1
        self._metrics.successful_requests += 1
        self._metrics.consecutive_successes += 1
        self._metrics.consecutive_failures = 0
        self._metrics.last_success_time = time.time()
        self._failure_window.append(True)

        if self._state == CircuitState.HALF_OPEN:
            self._half_open_calls += 1
            logger.info(
                "Circuit breaker half-open success",
                extra={
                    "provider": self.provider_name,
                    "half_open_calls": self._half_open_calls,
                    "max_calls": self.config.half_open_max_calls,
                },
            )
            # If we get enough successes in half-open, close the circuit
            if self._half_open_calls >= self.config.half_open_max_calls:
                self._transition_to_closed()

    def record_failure(self) -> None:
        """Record a failed request."""
        self._metrics.total_requests += 1
        self._metrics.failed_requests += 1
        self._metrics.consecutive_failures += 1
        self._metrics.consecutive_successes = 0
        self._metrics.last_failure_time = time.time()
        self._failure_window.append(False)

        if self._state == CircuitState.HALF_OPEN:
            # If we fail in half-open, go back to open
            self._transition_to_open()
        elif self._state == CircuitState.CLOSED:
            # Check if we should trip the circuit
            if self._should_trip():
                self._transition_to_open()

    def can_execute(self) -> bool:
        """Check if requests can execute through the circuit breaker.

        Returns:
            True if requests can execute, False if circuit is open
        """
        if self._state == CircuitState.CLOSED:
            return True

        if self._state == CircuitState.OPEN:
            # Check if we should attempt recovery
            if self._should_attempt_recovery():
                self._transition_to_half_open()
                return True
            return False

        if self._state == CircuitState.HALF_OPEN:
            # Allow limited requests in half-open state
            return self._half_open_calls < self.config.half_open_max_calls

        return False

    def _should_trip(self) -> bool:
        """Check if circuit should trip based on failure rate.

        Returns:
            True if circuit should trip
        """
        # Need minimum requests before considering failure rate
        if self._metrics.total_requests < self.config.minimum_requests:
            return False

        # Check if failure rate exceeds threshold
        failure_rate = self._metrics.failure_rate
        if failure_rate >= self.config.failure_rate_threshold:
            logger.warning(
                "Circuit breaker failure rate threshold exceeded",
                extra={
                    "provider": self.provider_name,
                    "failure_rate": failure_rate,
                    "threshold": self.config.failure_rate_threshold,
                    "total_requests": self._metrics.total_requests,
                },
            )
            return True

        return False

    def _should_attempt_recovery(self) -> bool:
        """Check if we should attempt recovery from open state.

        Returns:
            True if we should transition to half-open
        """
        if self._open_timestamp is None:
            return False

        elapsed = time.time() - self._open_timestamp
        return elapsed >= self.config.open_timeout_seconds

    def _transition_to_open(self) -> None:
        """Transition circuit to open state."""
        old_state = self._state
        self._state = CircuitState.OPEN
        self._open_timestamp = time.time()
        self._half_open_calls = 0

        logger.error(
            "Circuit breaker opened",
            extra={
                "provider": self.provider_name,
                "old_state": old_state.value,
                "new_state": self._state.value,
                "failure_rate": self._metrics.failure_rate,
                "total_requests": self._metrics.total_requests,
            },
        )

    def _transition_to_half_open(self) -> None:
        """Transition circuit to half-open state."""
        old_state = self._state
        self._state = CircuitState.HALF_OPEN
        self._half_open_calls = 0

        logger.info(
            "Circuit breaker transitioned to half-open",
            extra={
                "provider": self.provider_name,
                "old_state": old_state.value,
                "new_state": self._state.value,
                "open_duration_seconds": time.time() - (self._open_timestamp or 0),
            },
        )

    def _transition_to_closed(self) -> None:
        """Transition circuit to closed state."""
        old_state = self._state
        self._state = CircuitState.CLOSED
        self._open_timestamp = None
        self._half_open_calls = 0

        logger.info(
            "Circuit breaker closed",
            extra={
                "provider": self.provider_name,
                "old_state": old_state.value,
                "new_state": self._state.value,
                "total_requests": self._metrics.total_requests,
            },
        )

    def reset(self) -> None:
        """Reset circuit breaker to initial state."""
        old_state = self._state
        self._state = CircuitState.CLOSED
        self._metrics = CircuitBreakerMetrics()
        self._failure_window.clear()
        self._open_timestamp = None
        self._half_open_calls = 0

        logger.info(
            "Circuit breaker reset",
            extra={
                "provider": self.provider_name,
                "old_state": old_state.value,
                "new_state": self._state.value,
            },
        )

    def get_status(self) -> dict[str, Any]:
        """Get current circuit breaker status.

        Returns:
            Dictionary with status information
        """
        return {
            "provider": self.provider_name,
            "state": self._state.value,
            "can_execute": self.can_execute(),
            "metrics": self._metrics.to_dict(),
            "config": {
                "failure_rate_threshold": self.config.failure_rate_threshold,
                "minimum_requests": self.config.minimum_requests,
                "open_timeout_seconds": self.config.open_timeout_seconds,
                "half_open_max_calls": self.config.half_open_max_calls,
            },
        }
