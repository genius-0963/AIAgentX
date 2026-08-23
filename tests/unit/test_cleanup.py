"""Unit tests for cleanup service."""

from datetime import UTC, datetime, timedelta

import pytest

from app.application.services.cleanup_service import CleanupResult, CleanupService


@pytest.fixture
def mock_run_repository():
    """Mock run repository."""
    from unittest.mock import AsyncMock, MagicMock

    repo = MagicMock()
    repo.list = AsyncMock(return_value=[])
    return repo


@pytest.fixture
def cleanup_service(mock_run_repository):
    """Create cleanup service with mocked repository."""
    return CleanupService(run_repository=mock_run_repository, retention_days=30)


@pytest.mark.asyncio
async def test_cleanup_expired_runs(cleanup_service, mock_run_repository):
    """Test cleanup of expired runs."""
    older_than = datetime.now(UTC) - timedelta(days=35)

    result = await cleanup_service.cleanup_expired_runs(older_than)

    assert result.success is True
    assert result.items_processed >= 0
    assert result.duration_seconds >= 0


@pytest.mark.asyncio
async def test_cleanup_expired_runs_default_retention(cleanup_service):
    """Test cleanup with default retention period."""
    result = await cleanup_service.cleanup_expired_runs()

    assert result.success is True


@pytest.mark.asyncio
async def test_recover_expired_leases(cleanup_service):
    """Test recovery of expired leases."""
    result = await cleanup_service.recover_expired_leases()

    assert result.success is True
    assert result.items_processed >= 0


@pytest.mark.asyncio
async def test_cleanup_old_events(cleanup_service):
    """Test cleanup of old events."""
    older_than = datetime.now(UTC) - timedelta(days=35)

    result = await cleanup_service.cleanup_old_events(older_than)

    assert result.success is True
    assert result.items_processed >= 0


@pytest.mark.asyncio
async def test_cleanup_expired_idempotency_keys(cleanup_service):
    """Test cleanup of expired idempotency keys."""
    result = await cleanup_service.cleanup_expired_idempotency_keys()

    assert result.success is True
    assert result.items_processed >= 0


@pytest.mark.asyncio
async def test_cleanup_session_data(cleanup_service):
    """Test cleanup of session data."""
    result = await cleanup_service.cleanup_session_data()

    assert result.success is True
    assert result.items_processed >= 0


@pytest.mark.asyncio
async def test_run_all_cleanup_jobs(cleanup_service):
    """Test running all cleanup jobs."""
    results = await cleanup_service.run_all_cleanup_jobs()

    assert "expired_runs" in results
    assert "lease_recovery" in results
    assert "old_events" in results
    assert "idempotency_keys" in results
    assert "session_data" in results

    # All jobs should succeed
    for _job_name, result in results.items():
        assert result.success is True


def test_set_retention_days(cleanup_service):
    """Test updating retention period."""
    cleanup_service.set_retention_days(60)

    # The retention period should be updated
    assert cleanup_service._retention_days == 60


def test_cleanup_result_success():
    """Test CleanupResult for successful operation."""
    result = CleanupResult(
        success=True,
        items_processed=10,
        items_deleted=8,
        duration_seconds=1.5,
    )

    assert result.success is True
    assert result.items_processed == 10
    assert result.items_deleted == 8


def test_cleanup_result_failure():
    """Test CleanupResult for failed operation."""
    result = CleanupResult(
        success=False,
        items_processed=5,
        items_deleted=0,
        errors=["Database connection failed"],
        duration_seconds=0.5,
    )

    assert result.success is False
    assert result.errors == ["Database connection failed"]
