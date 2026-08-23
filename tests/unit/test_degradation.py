"""Unit tests for degradation service."""

from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

from app.application.services.degradation_service import (
    DegradationMode,
    DegradationService,
    DegradationStatus,
)


@pytest.fixture
def mock_settings():
    """Mock settings."""
    settings = MagicMock()
    settings.degradation_auto_recovery = True
    return settings


@pytest.fixture
def degradation_service(mock_settings):
    """Create degradation service with mocked settings."""
    return DegradationService(
        settings=mock_settings,
        database_failure_threshold=5,
        redis_failure_threshold=3,
    )


@pytest.mark.asyncio
async def test_handle_database_failure_below_threshold(degradation_service):
    """Test database failure below threshold."""
    status = await degradation_service.handle_database_failure()

    assert status.mode == DegradationMode.FULL
    assert degradation_service._db_failure_count == 1


@pytest.mark.asyncio
async def test_handle_database_failure_at_threshold(degradation_service):
    """Test database failure at threshold triggers degradation."""
    # Set failure count to threshold - 1
    degradation_service._db_failure_count = 4

    status = await degradation_service.handle_database_failure()

    assert status.mode == DegradationMode.DEGRADED_DB
    assert status.reason is not None
    assert "database" in status.affected_components


@pytest.mark.asyncio
async def test_handle_redis_failure_below_threshold(degradation_service):
    """Test Redis failure below threshold."""
    status = await degradation_service.handle_redis_failure()

    assert status.mode == DegradationMode.FULL
    assert degradation_service._redis_failure_count == 1


@pytest.mark.asyncio
async def test_handle_redis_failure_at_threshold(degradation_service):
    """Test Redis failure at threshold triggers degradation."""
    # Set failure count to threshold - 1
    degradation_service._redis_failure_count = 2

    status = await degradation_service.handle_redis_failure()

    assert status.mode == DegradationMode.DEGRADED_CACHE
    assert status.reason is not None
    assert "cache" in status.affected_components


@pytest.mark.asyncio
async def test_handle_provider_failure(degradation_service):
    """Test provider failure tracking."""
    status = await degradation_service.handle_provider_failure("openai")

    assert status.mode == DegradationMode.FULL
    assert degradation_service._provider_failures["openai"] == 1


@pytest.mark.asyncio
async def test_enter_degradation_mode(degradation_service):
    """Test entering degradation mode."""
    status = await degradation_service._enter_degradation_mode(
        DegradationMode.DEGRADED_DB,
        reason="Test degradation",
        affected_components=["database"],
    )

    assert status.mode == DegradationMode.DEGRADED_DB
    assert status.reason == "Test degradation"
    assert status.entered_at is not None


@pytest.mark.asyncio
async def test_exit_degradation_mode(degradation_service):
    """Test exiting degradation mode."""
    # First enter degradation mode
    await degradation_service._enter_degradation_mode(
        DegradationMode.DEGRADED_CACHE,
        reason="Test",
        affected_components=["cache"],
    )

    # Then exit
    status = await degradation_service.exit_degradation_mode()

    assert status.mode == DegradationMode.FULL
    assert degradation_service._db_failure_count == 0
    assert degradation_service._redis_failure_count == 0


@pytest.mark.asyncio
async def test_check_recovery_conditions_full_mode(degradation_service):
    """Test recovery check when already in full mode."""
    can_recover = await degradation_service.check_recovery_conditions()

    assert can_recover is True


@pytest.mark.asyncio
async def test_check_recovery_conditions_degraded_mode(degradation_service):
    """Test recovery check when in degraded mode."""
    # Enter degraded mode
    await degradation_service._enter_degradation_mode(
        DegradationMode.DEGRADED_DB,
        reason="Test",
        affected_components=["database"],
    )

    # With DB failures, recovery should not be possible
    can_recover = await degradation_service.check_recovery_conditions()

    assert can_recover is False


@pytest.mark.asyncio
async def test_get_current_status(degradation_service):
    """Test getting current degradation status."""
    status = await degradation_service.get_current_status()

    assert status.mode == DegradationMode.FULL
    assert status.entered_at is not None


def test_get_degraded_features_full_mode(degradation_service):
    """Test getting degraded features in full mode."""
    features = degradation_service.get_degraded_features()

    assert features == []


def test_get_degraded_features_cache_mode(degradation_service):
    """Test getting degraded features in cache degradation mode."""
    degradation_service._current_status = DegradationStatus(
        mode=DegradationMode.DEGRADED_CACHE,
        reason="Test",
        entered_at=datetime.now(UTC),
    )

    features = degradation_service.get_degraded_features()

    assert "rate_limiting" in features
    assert "idempotency" in features


def test_is_feature_available_full_mode(degradation_service):
    """Test feature availability in full mode."""
    assert degradation_service.is_feature_available("rate_limiting") is True
    assert degradation_service.is_feature_available("idempotency") is True


def test_is_feature_available_degraded_mode(degradation_service):
    """Test feature availability in degraded mode."""
    degradation_service._current_status = DegradationStatus(
        mode=DegradationMode.DEGRADED_CACHE,
        reason="Test",
        entered_at=datetime.now(UTC),
    )

    assert degradation_service.is_feature_available("rate_limiting") is False
    assert degradation_service.is_feature_available("basic_run") is True


@pytest.mark.asyncio
async def test_manual_degradation(degradation_service):
    """Test manual degradation entry."""
    status = await degradation_service.manual_degradation(
        DegradationMode.MINIMAL,
        reason="Operational maintenance",
    )

    assert status.mode == DegradationMode.MINIMAL
    assert "Manual degradation" in status.reason


@pytest.mark.asyncio
async def test_reset_failure_counters(degradation_service):
    """Test resetting failure counters."""
    degradation_service._db_failure_count = 5
    degradation_service._redis_failure_count = 3
    degradation_service._provider_failures["openai"] = 2

    await degradation_service.reset_failure_counters()

    assert degradation_service._db_failure_count == 0
    assert degradation_service._redis_failure_count == 0
    assert degradation_service._provider_failures == {}
