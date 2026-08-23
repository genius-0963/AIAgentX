"""Unit tests for rate limiting service."""

from uuid import uuid4

import pytest

from app.application.services.rate_limit_service import RateLimitResult, RateLimitService


@pytest.fixture
def mock_rate_limiter():
    """Mock rate limiter."""
    from unittest.mock import AsyncMock, MagicMock

    limiter = MagicMock()
    limiter.check_rate_limit = AsyncMock(
        return_value={"allowed": True, "remaining": 50, "reset_at": 1234567890}
    )
    limiter.check_concurrency = AsyncMock(return_value={"allowed": True, "remaining": 5})
    limiter.record_request = AsyncMock(return_value=True)
    limiter.increment_concurrency = AsyncMock(return_value={"current": 1, "remaining": 4})
    limiter.decrement_concurrency = AsyncMock(return_value={"current": 0, "remaining": 5})
    limiter.get_current_usage = AsyncMock(return_value={"remaining": 50, "reset_at": 1234567890})
    limiter.health_check = AsyncMock(return_value=True)
    return limiter


@pytest.fixture
def rate_limit_service(mock_rate_limiter):
    """Create rate limit service with mocked limiter."""
    return RateLimitService(rate_limiter=mock_rate_limiter)


@pytest.mark.asyncio
async def test_check_rate_limit_allowed(rate_limit_service, mock_rate_limiter):
    """Test rate limit check when allowed."""
    mock_rate_limiter.check_rate_limit.return_value = {
        "allowed": True,
        "remaining": 50,
        "reset_at": 1234567890,
    }

    result = await rate_limit_service.check_rate_limit(uuid4(), "/v1/runs", "free")

    assert result.allowed is True
    assert result.remaining == 50
    assert result.limit == 60  # Default for free plan


@pytest.mark.asyncio
async def test_check_rate_limit_exceeded(rate_limit_service, mock_rate_limiter):
    """Test rate limit check when exceeded."""
    mock_rate_limiter.check_rate_limit.return_value = {
        "allowed": False,
        "remaining": 0,
        "reset_at": 1234567890,
    }

    result = await rate_limit_service.check_rate_limit(uuid4(), "/v1/runs", "free")

    assert result.allowed is False
    assert result.remaining == 0
    assert result.reason == "Rate limit exceeded"


@pytest.mark.asyncio
async def test_check_concurrent_runs_allowed(rate_limit_service, mock_rate_limiter):
    """Test concurrent run check when allowed."""
    mock_rate_limiter.check_concurrency.return_value = {
        "allowed": True,
        "remaining": 4,
    }

    result = await rate_limit_service.check_concurrent_runs(uuid4(), "free")

    assert result.allowed is True
    assert result.remaining == 4
    assert result.limit == 5  # Default for free plan


@pytest.mark.asyncio
async def test_check_concurrent_runs_exceeded(rate_limit_service, mock_rate_limiter):
    """Test concurrent run check when exceeded."""
    mock_rate_limiter.check_concurrency.return_value = {
        "allowed": False,
        "remaining": 0,
    }

    result = await rate_limit_service.check_concurrent_runs(uuid4(), "free")

    assert result.allowed is False
    assert result.reason == "Concurrent run limit exceeded"


@pytest.mark.asyncio
async def test_check_global_concurrency(rate_limit_service, mock_rate_limiter):
    """Test global concurrency check."""
    mock_rate_limiter.check_concurrency.return_value = {
        "allowed": True,
        "remaining": 900,
    }

    result = await rate_limit_service.check_global_concurrency(1000)

    assert result.allowed is True
    assert result.remaining == 900
    assert result.limit == 1000


@pytest.mark.asyncio
async def test_record_request(rate_limit_service, mock_rate_limiter):
    """Test recording a request."""
    await rate_limit_service.record_request(uuid4(), "/v1/runs")

    mock_rate_limiter.record_request.assert_called_once()


@pytest.mark.asyncio
async def test_record_run_start(rate_limit_service, mock_rate_limiter):
    """Test recording run start."""
    await rate_limit_service.record_run_start(uuid4())

    assert mock_rate_limiter.increment_concurrency.call_count == 2  # Tenant + global


@pytest.mark.asyncio
async def test_record_run_end(rate_limit_service, mock_rate_limiter):
    """Test recording run end."""
    await rate_limit_service.record_run_end(uuid4())

    assert mock_rate_limiter.decrement_concurrency.call_count == 2  # Tenant + global


@pytest.mark.asyncio
async def test_get_rate_limit_headers(rate_limit_service, mock_rate_limiter):
    """Test getting rate limit headers."""
    mock_rate_limiter.get_current_usage.return_value = {
        "remaining": 50,
        "reset_at": 1234567890,
    }

    headers = await rate_limit_service.get_rate_limit_headers(uuid4(), "/v1/runs", "free")

    assert headers["X-RateLimit-Limit"] == "60"
    assert headers["X-RateLimit-Remaining"] == "50"
    assert headers["X-RateLimit-Reset"] == "1234567890"


@pytest.mark.asyncio
async def test_update_plan_limits(rate_limit_service):
    """Test updating plan limits."""
    rate_limit_service.update_plan_limits(
        "premium", {"requests_per_minute": 500, "concurrent_runs": 25}
    )

    # Verify the update (would need to check internal state)
    # For now, just ensure it doesn't raise an error


@pytest.mark.asyncio
async def test_health_check(rate_limit_service, mock_rate_limiter):
    """Test health check."""
    result = await rate_limit_service.health_check()

    assert result is True
    mock_rate_limiter.health_check.assert_called_once()


def test_rate_limit_result_allowed():
    """Test RateLimitResult for allowed request."""
    result = RateLimitResult(allowed=True, remaining=50, reset_at=1234567890, limit=60)

    assert result.allowed is True
    assert result.remaining == 50


def test_rate_limit_result_denied():
    """Test RateLimitResult for denied request."""
    result = RateLimitResult(
        allowed=False,
        remaining=0,
        reset_at=1234567890,
        limit=60,
        reason="Rate limit exceeded",
    )

    assert result.allowed is False
    assert result.reason == "Rate limit exceeded"
