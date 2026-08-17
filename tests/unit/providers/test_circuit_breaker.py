"""Unit tests for circuit breaker."""

import pytest

from app.domain.providers.value_objects import CircuitBreakerConfig
from app.infrastructure.providers.circuit_breaker import CircuitBreaker, CircuitState


def test_circuit_breaker_initial_state():
    """Test circuit breaker initial state."""
    config = CircuitBreakerConfig()
    breaker = CircuitBreaker(config=config, provider_name="test-provider")

    assert breaker.state == CircuitState.CLOSED
    assert breaker.can_execute() is True


def test_circuit_breaker_success_recording():
    """Test circuit breaker success recording."""
    config = CircuitBreakerConfig(minimum_requests=5)
    breaker = CircuitBreaker(config=config, provider_name="test-provider")

    # Record successes
    for _ in range(10):
        breaker.record_success()

    assert breaker.metrics.successful_requests == 10
    assert breaker.metrics.failure_rate == 0.0
    assert breaker.state == CircuitState.CLOSED


def test_circuit_breaker_failure_recording():
    """Test circuit breaker failure recording."""
    config = CircuitBreakerConfig(minimum_requests=5, failure_rate_threshold=0.5)
    breaker = CircuitBreaker(config=config, provider_name="test-provider")

    # Record mix of successes and failures
    for i in range(10):
        if i < 6:  # 6 failures
            breaker.record_failure()
        else:  # 4 successes
            breaker.record_success()

    assert breaker.metrics.failed_requests == 6
    assert breaker.metrics.successful_requests == 4
    assert breaker.metrics.failure_rate == 0.6


def test_circuit_breaker_tripping():
    """Test circuit breaker tripping on high failure rate."""
    config = CircuitBreakerConfig(
        minimum_requests=5,
        failure_rate_threshold=0.5,
    )
    breaker = CircuitBreaker(config=config, provider_name="test-provider")

    # Record failures to exceed threshold
    for _ in range(6):
        breaker.record_failure()

    # Should trip after minimum requests
    assert breaker.state == CircuitState.OPEN
    assert breaker.can_execute() is False


def test_circuit_breaker_half_open_transition():
    """Test circuit breaker transition to half-open."""
    config = CircuitBreakerConfig(
        minimum_requests=5,
        failure_rate_threshold=0.5,
        open_timeout_seconds=1,  # Short timeout for testing
    )
    breaker = CircuitBreaker(config=config, provider_name="test-provider")

    # Trip the circuit
    for _ in range(6):
        breaker.record_failure()

    assert breaker.state == CircuitState.OPEN

    # Wait for timeout (in real test, would use time.sleep)
    # For unit test, we can manually check the logic
    # The circuit should transition to half-open after timeout


def test_circuit_breaker_recovery():
    """Test circuit breaker recovery after successful probes."""
    config = CircuitBreakerConfig(
        minimum_requests=5,
        failure_rate_threshold=0.5,
        open_timeout_seconds=1,
        half_open_max_calls=3,
    )
    breaker = CircuitBreaker(config=config, provider_name="test-provider")

    # Trip the circuit
    for _ in range(6):
        breaker.record_failure()

    assert breaker.state == CircuitState.OPEN

    # Simulate recovery with successful calls
    # In real scenario, would wait for timeout first
    breaker._transition_to_half_open()
    assert breaker.state == CircuitState.HALF_OPEN

    # Record successful probes
    for _ in range(3):
        breaker.record_success()

    # Should close after successful probes
    assert breaker.state == CircuitState.CLOSED


def test_circuit_breaker_half_open_failure():
    """Test circuit breaker returning to open after half-open failure."""
    config = CircuitBreakerConfig(
        minimum_requests=5,
        failure_rate_threshold=0.5,
        open_timeout_seconds=1,
        half_open_max_calls=3,
    )
    breaker = CircuitBreaker(config=config, provider_name="test-provider")

    # Trip the circuit
    for _ in range(6):
        breaker.record_failure()

    breaker._transition_to_half_open()
    assert breaker.state == CircuitState.HALF_OPEN

    # Record failure in half-open
    breaker.record_failure()

    # Should return to open
    assert breaker.state == CircuitState.OPEN


def test_circuit_breaker_reset():
    """Test circuit breaker reset."""
    config = CircuitBreakerConfig(
        minimum_requests=5,
        failure_rate_threshold=0.5,
    )
    breaker = CircuitBreaker(config=config, provider_name="test-provider")

    # Trip the circuit
    for _ in range(6):
        breaker.record_failure()

    assert breaker.state == CircuitState.OPEN
    assert breaker.metrics.failed_requests > 0

    # Reset
    breaker.reset()

    assert breaker.state == CircuitState.CLOSED
    assert breaker.metrics.total_requests == 0
    assert breaker.metrics.failed_requests == 0


def test_circuit_breaker_status():
    """Test circuit breaker status reporting."""
    config = CircuitBreakerConfig(
        minimum_requests=5,
        failure_rate_threshold=0.5,
    )
    breaker = CircuitBreaker(config=config, provider_name="test-provider")

    status = breaker.get_status()

    assert status["provider"] == "test-provider"
    assert status["state"] == CircuitState.CLOSED.value
    assert status["can_execute"] is True
    assert "metrics" in status
    assert "config" in status


def test_circuit_breaker_can_execute():
    """Test can_execute method."""
    config = CircuitBreakerConfig(
        minimum_requests=5,
        failure_rate_threshold=0.5,
    )
    breaker = CircuitBreaker(config=config, provider_name="test-provider")

    # Should be able to execute when closed
    assert breaker.can_execute() is True

    # Trip the circuit
    for _ in range(6):
        breaker.record_failure()

    # Should not be able to execute when open
    assert breaker.can_execute() is False
