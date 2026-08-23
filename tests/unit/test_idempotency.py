"""Unit tests for idempotency service."""

from uuid import uuid4

import pytest

from app.application.services.idempotency_service import IdempotencyResult, IdempotencyService


@pytest.fixture
def mock_idempotency_store():
    """Mock idempotency store."""
    from unittest.mock import AsyncMock, MagicMock

    store = MagicMock()
    store.get = AsyncMock(return_value=None)
    store.set = AsyncMock(return_value=True)
    store.set_response = AsyncMock(return_value=True)
    store.delete = AsyncMock(return_value=True)
    store.exists = AsyncMock(return_value=False)
    store.health_check = AsyncMock(return_value=True)
    return store


@pytest.fixture
def idempotency_service(mock_idempotency_store):
    """Create idempotency service with mocked store."""
    return IdempotencyService(idempotency_store=mock_idempotency_store, ttl_seconds=86400)


@pytest.mark.asyncio
async def test_check_and_store_new_request(idempotency_service, mock_idempotency_store):
    """Test idempotency check for new request."""
    mock_idempotency_store.get.return_value = None

    result = await idempotency_service.check_and_store(
        key="test-key",
        tenant_id=uuid4(),
        operation="POST /v1/runs",
        request_data={"test": "data"},
    )

    assert result.is_duplicate is False
    assert result.key_exists is False
    mock_idempotency_store.set.assert_called_once()


@pytest.mark.asyncio
async def test_check_and_store_duplicate_request(idempotency_service, mock_idempotency_store):
    """Test idempotency check for duplicate request."""
    mock_idempotency_store.get.return_value = {
        "response": {"id": "run-123", "state": "queued"},
        "request_id": "req-456",
    }

    result = await idempotency_service.check_and_store(
        key="test-key",
        tenant_id=uuid4(),
        operation="POST /v1/runs",
    )

    assert result.is_duplicate is True
    assert result.key_exists is True
    assert result.cached_response == {"id": "run-123", "state": "queued"}
    assert result.original_request_id == "req-456"


@pytest.mark.asyncio
async def test_get_response_cached(idempotency_service, mock_idempotency_store):
    """Test getting cached response."""
    mock_idempotency_store.get.return_value = {
        "response": {"id": "run-123", "state": "completed"},
    }

    response = await idempotency_service.get_response("test-key", uuid4())

    assert response == {"id": "run-123", "state": "completed"}


@pytest.mark.asyncio
async def test_get_response_not_cached(idempotency_service, mock_idempotency_store):
    """Test getting response when not cached."""
    mock_idempotency_store.get.return_value = None

    response = await idempotency_service.get_response("test-key", uuid4())

    assert response is None


@pytest.mark.asyncio
async def test_store_response(idempotency_service, mock_idempotency_store):
    """Test storing response."""
    mock_idempotency_store.get.return_value = {"created_at": "2024-01-01T00:00:00"}

    result = await idempotency_service.store_response(
        key="test-key",
        tenant_id=uuid4(),
        response={"id": "run-123", "state": "completed"},
        request_id="req-789",
    )

    assert result is True
    mock_idempotency_store.set_response.assert_called_once()


@pytest.mark.asyncio
async def test_store_response_not_found(idempotency_service, mock_idempotency_store):
    """Test storing response when key not found."""
    mock_idempotency_store.get.return_value = None

    result = await idempotency_service.store_response(
        key="test-key",
        tenant_id=uuid4(),
        response={"id": "run-123"},
    )

    assert result is False


@pytest.mark.asyncio
async def test_invalidate_key(idempotency_service, mock_idempotency_store):
    """Test invalidating idempotency key."""
    result = await idempotency_service.invalidate_key("test-key", uuid4())

    assert result is True
    mock_idempotency_store.delete.assert_called_once()


@pytest.mark.asyncio
async def test_expire_keys(idempotency_service):
    """Test expiring old keys."""
    from datetime import UTC, datetime, timedelta

    older_than = datetime.now(UTC) - timedelta(days=1)
    result = await idempotency_service.expire_keys(uuid4(), older_than)

    # Currently returns 0 as we rely on Redis TTL
    assert result == 0


@pytest.mark.asyncio
async def test_health_check(idempotency_service, mock_idempotency_store):
    """Test health check."""
    result = await idempotency_service.health_check()

    assert result is True
    mock_idempotency_store.health_check.assert_called_once()


def test_idempotency_result_allowed():
    """Test IdempotencyResult for allowed request."""
    result = IdempotencyResult(is_duplicate=False, key_exists=False)

    assert result.is_duplicate is False
    assert result.cached_response is None
    assert result.key_exists is False


def test_idempotency_result_duplicate():
    """Test IdempotencyResult for duplicate request."""
    result = IdempotencyResult(
        is_duplicate=True,
        cached_response={"id": "run-123"},
        key_exists=True,
        original_request_id="req-456",
    )

    assert result.is_duplicate is True
    assert result.cached_response == {"id": "run-123"}
    assert result.key_exists is True
    assert result.original_request_id == "req-456"
