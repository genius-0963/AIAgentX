"""Unit tests for retry logic."""

import pytest

from app.domain.providers.value_objects import RetryPolicy
from app.infrastructure.providers.retry import classify_error, calculate_backoff, ErrorType


def test_classify_error_timeout():
    """Test error classification for timeout."""
    import httpx

    error = httpx.TimeoutException("Request timed out")
    provider_error = classify_error(error)

    assert provider_error.is_retryable is True
    assert provider_error.error_type == ErrorType.TIMEOUT.value


def test_classify_error_rate_limit():
    """Test error classification for rate limit."""
    import httpx

    # Create a mock response with 429 status
    response = httpx.Response(429, request=httpx.Request("GET", "http://test.com"))
    error = httpx.HTTPStatusError("Rate limit", request=response.request, response=response)
    provider_error = classify_error(error)

    assert provider_error.is_retryable is True
    assert provider_error.error_type == ErrorType.RATE_LIMIT.value


def test_classify_error_server_error():
    """Test error classification for server error."""
    import httpx

    response = httpx.Response(500, request=httpx.Request("GET", "http://test.com"))
    error = httpx.HTTPStatusError("Server error", request=response.request, response=response)
    provider_error = classify_error(error)

    assert provider_error.is_retryable is True
    assert provider_error.error_type == ErrorType.SERVER_ERROR.value


def test_classify_error_auth_error():
    """Test error classification for auth error."""
    import httpx

    response = httpx.Response(401, request=httpx.Request("GET", "http://test.com"))
    error = httpx.HTTPStatusError("Auth error", request=response.request, response=response)
    provider_error = classify_error(error)

    assert provider_error.is_retryable is False
    assert provider_error.error_type == ErrorType.AUTH_ERROR.value


def test_classify_error_validation_error():
    """Test error classification for validation error."""
    import httpx

    response = httpx.Response(400, request=httpx.Request("GET", "http://test.com"))
    error = httpx.HTTPStatusError("Validation error", request=response.request, response=response)
    provider_error = classify_error(error)

    assert provider_error.is_retryable is False
    assert provider_error.error_type == ErrorType.VALIDATION_ERROR.value


def test_classify_error_network_error():
    """Test error classification for network error."""
    import httpx

    error = httpx.ConnectError("Connection failed")
    provider_error = classify_error(error)

    assert provider_error.is_retryable is True
    assert provider_error.error_type == ErrorType.NETWORK_ERROR.value


def test_calculate_backoff_no_jitter():
    """Test backoff calculation without jitter."""
    policy = RetryPolicy(
        initial_backoff_ms=1000,
        max_backoff_ms=10000,
        backoff_multiplier=2.0,
        jitter=False,
    )

    # First attempt
    backoff = calculate_backoff(0, policy)
    assert backoff == 1000

    # Second attempt
    backoff = calculate_backoff(1, policy)
    assert backoff == 2000

    # Third attempt
    backoff = calculate_backoff(2, policy)
    assert backoff == 4000


def test_calculate_backoff_with_jitter():
    """Test backoff calculation with jitter."""
    policy = RetryPolicy(
        initial_backoff_ms=1000,
        max_backoff_ms=10000,
        backoff_multiplier=2.0,
        jitter=True,
    )

    # With jitter, should be between 0 and calculated backoff
    backoff = calculate_backoff(0, policy)
    assert 0 <= backoff <= 1000

    backoff = calculate_backoff(1, policy)
    assert 0 <= backoff <= 2000


def test_calculate_backoff_max_cap():
    """Test backoff calculation with max cap."""
    policy = RetryPolicy(
        initial_backoff_ms=1000,
        max_backoff_ms=5000,
        backoff_multiplier=3.0,
        jitter=False,
    )

    # Should cap at max_backoff_ms
    backoff = calculate_backoff(2, policy)
    assert backoff == 5000  # Capped

    backoff = calculate_backoff(10, policy)
    assert backoff == 5000  # Still capped


def test_retry_policy_validation():
    """Test RetryPolicy validation."""
    # Valid policy
    policy = RetryPolicy(
        max_retries=3,
        initial_backoff_ms=1000,
        max_backoff_ms=10000,
        backoff_multiplier=2.0,
    )
    assert policy.max_retries == 3

    # Invalid: negative max retries
    with pytest.raises(ValueError, match="Max retries cannot be negative"):
        RetryPolicy(max_retries=-1)

    # Invalid: negative initial backoff
    with pytest.raises(ValueError, match="Initial backoff must be positive"):
        RetryPolicy(initial_backoff_ms=-1)

    # Invalid: backoff multiplier <= 1
    with pytest.raises(ValueError, match="Backoff multiplier must be greater than"):
        RetryPolicy(backoff_multiplier=1.0)
