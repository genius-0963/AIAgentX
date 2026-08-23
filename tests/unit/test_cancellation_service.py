"""Unit tests for cancellation service."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.application.services.cancellation_service import CancellationService
from app.domain.entities.run import Run
from app.domain.value_objects.money import Money
from app.domain.value_objects.state import RunState


@pytest.fixture
def mock_run_repository():
    """Mock run repository."""
    from unittest.mock import AsyncMock, MagicMock

    repo = MagicMock()
    repo.get = AsyncMock()
    repo.update = AsyncMock()
    repo.request_cancellation = AsyncMock()
    return repo


@pytest.fixture
def mock_cancellation_signals():
    """Mock cancellation signals."""
    from unittest.mock import AsyncMock, MagicMock

    signals = MagicMock()
    signals.publish_request = AsyncMock(return_value=True)
    signals.publish_acknowledgement = AsyncMock(return_value=True)
    signals.publish_completion = AsyncMock(return_value=True)
    signals.check_flag = AsyncMock(return_value=False)
    signals.set_flag = AsyncMock(return_value=True)
    signals.cleanup = AsyncMock(return_value=True)
    return signals


@pytest.fixture
def mock_settings():
    """Mock settings."""
    from unittest.mock import MagicMock

    settings = MagicMock()
    settings.cancellation_timeout_seconds = 30
    return settings


@pytest.fixture
def cancellation_service(mock_run_repository, mock_cancellation_signals, mock_settings):
    """Create cancellation service with mocked dependencies."""
    return CancellationService(
        run_repository=mock_run_repository,
        cancellation_signals=mock_cancellation_signals,
        settings=mock_settings,
    )


@pytest.fixture
def sample_run():
    """Create a sample run entity."""
    return Run(
        id=uuid4(),
        tenant_id=uuid4(),
        agent_version_id=uuid4(),
        state=RunState.RUNNING,
        input_data={"question": "test"},
        idempotency_key="test-key",
        max_steps=100,
        max_cost=Money(10_000_000),
        spent_cost=Money(5_000_000),
        timeout_seconds=90,
    )


@pytest.mark.asyncio
async def test_request_cancellation_success(
    cancellation_service,
    sample_run,
    mock_run_repository,
    mock_cancellation_signals,
):
    """Test successful cancellation request."""
    mock_run_repository.get.return_value = sample_run
    mock_run_repository.update.return_value = sample_run

    result = await cancellation_service.request_cancellation(sample_run.id, "User requested")

    assert result is True
    assert sample_run.cancel_requested_at is not None
    mock_cancellation_signals.publish_request.assert_called_once()
    mock_cancellation_signals.set_flag.assert_called_once()


@pytest.mark.asyncio
async def test_request_cancellation_run_not_found(cancellation_service, mock_run_repository):
    """Test cancellation request when run not found."""
    mock_run_repository.get.return_value = None

    result = await cancellation_service.request_cancellation(uuid4())

    assert result is False


@pytest.mark.asyncio
async def test_request_cancellation_terminal_state(
    cancellation_service,
    sample_run,
    mock_run_repository,
):
    """Test cancellation request when run is already in terminal state."""
    sample_run.state = RunState.SUCCEEDED
    mock_run_repository.get.return_value = sample_run

    result = await cancellation_service.request_cancellation(sample_run.id)

    assert result is True  # Idempotent


@pytest.mark.asyncio
async def test_is_cancelled_via_flag(cancellation_service, mock_cancellation_signals):
    """Test cancellation check via Redis flag."""
    mock_cancellation_signals.check_flag.return_value = True

    result = await cancellation_service.is_cancelled(uuid4())

    assert result is True


@pytest.mark.asyncio
async def test_is_cancelled_via_database(
    cancellation_service,
    sample_run,
    mock_run_repository,
    mock_cancellation_signals,
):
    """Test cancellation check via database when flag not set."""
    mock_cancellation_signals.check_flag.return_value = False
    sample_run.cancel_requested_at = datetime.now(UTC)
    mock_run_repository.get.return_value = sample_run

    result = await cancellation_service.is_cancelled(sample_run.id)

    assert result is True


@pytest.mark.asyncio
async def test_is_cancelled_not_cancelled(
    cancellation_service,
    sample_run,
    mock_run_repository,
    mock_cancellation_signals,
):
    """Test cancellation check when run is not cancelled."""
    mock_cancellation_signals.check_flag.return_value = False
    sample_run.cancel_requested_at = None
    mock_run_repository.get.return_value = sample_run

    result = await cancellation_service.is_cancelled(sample_run.id)

    assert result is False


@pytest.mark.asyncio
async def test_acknowledge_cancellation(
    cancellation_service,
    sample_run,
    mock_run_repository,
    mock_cancellation_signals,
):
    """Test cancellation acknowledgement."""
    mock_run_repository.get.return_value = sample_run

    result = await cancellation_service.acknowledge_cancellation(sample_run.id, "worker-1")

    assert result is True
    mock_cancellation_signals.publish_acknowledgement.assert_called_once()


@pytest.mark.asyncio
async def test_complete_cancellation(
    cancellation_service,
    sample_run,
    mock_run_repository,
    mock_cancellation_signals,
):
    """Test cancellation completion."""
    mock_run_repository.get.return_value = sample_run
    mock_run_repository.update.return_value = sample_run

    result = await cancellation_service.complete_cancellation(
        sample_run.id, "worker-1", steps_cancelled=5, cleanup_performed=True
    )

    assert result is True
    assert sample_run.state == RunState.CANCELLED
    mock_cancellation_signals.publish_completion.assert_called_once()
    mock_cancellation_signals.cleanup.assert_called_once()


@pytest.mark.asyncio
async def test_check_cancellation_timeout(cancellation_service, sample_run, mock_run_repository):
    """Test cancellation timeout detection."""
    sample_run.cancel_requested_at = datetime.now(UTC) - timedelta(seconds=35)
    mock_run_repository.get.return_value = sample_run
    mock_run_repository.update.return_value = sample_run

    result = await cancellation_service.check_cancellation_timeout(sample_run.id)

    assert result is True


@pytest.mark.asyncio
async def test_check_cancellation_no_timeout(cancellation_service, sample_run, mock_run_repository):
    """Test cancellation timeout when not exceeded."""
    sample_run.cancel_requested_at = datetime.now(UTC) - timedelta(seconds=10)
    mock_run_repository.get.return_value = sample_run

    result = await cancellation_service.check_cancellation_timeout(sample_run.id)

    assert result is False


@pytest.mark.asyncio
async def test_cleanup_cancellation_resources(cancellation_service, mock_cancellation_signals):
    """Test cleanup of cancellation resources."""
    result = await cancellation_service.cleanup_cancellation_resources(uuid4())

    assert result is True
    mock_cancellation_signals.cleanup.assert_called_once()


@pytest.mark.asyncio
async def test_subscribe_to_cancellation(cancellation_service, mock_cancellation_signals):
    """Test subscription to cancellation signals."""
    async def mock_subscribe():
        yield {"signal_type": "request", "run_id": "test"}
        yield {"signal_type": "complete", "run_id": "test"}

    mock_cancellation_signals.subscribe.return_value = mock_subscribe()

    signals = []
    async for signal in cancellation_service.subscribe_to_cancellation(uuid4()):
        signals.append(signal)

    assert len(signals) == 2
