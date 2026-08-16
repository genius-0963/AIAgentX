"""Test Redis client wrapper."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.asyncio
async def test_check_redis_health_returns_true_on_pong() -> None:
    from app.infrastructure.cache.redis_client import check_redis_health

    mock_client = MagicMock()
    mock_client.ping = AsyncMock(return_value=True)
    result = await check_redis_health(mock_client)
    assert result is True


@pytest.mark.asyncio
async def test_check_redis_health_returns_false_on_error() -> None:
    from app.infrastructure.cache.redis_client import check_redis_health

    mock_client = MagicMock()
    mock_client.ping = AsyncMock(side_effect=Exception("connection refused"))
    result = await check_redis_health(mock_client)
    assert result is False


def test_create_redis_client_uses_settings() -> None:
    from app.infrastructure.cache.redis_client import create_redis_client
    from app.settings import Settings

    settings = Settings(
        _env_file=None,
        secret_key="x" * 32,
        database_url="postgresql+asyncpg://user:pass@localhost:5432/test",
        redis_url="redis://localhost:6379/1",
    )
    with patch("redis.asyncio.from_url") as mock_from_url:
        mock_from_url.return_value = MagicMock()
        create_redis_client(settings)
        assert mock_from_url.called
        call_args = mock_from_url.call_args
        url = call_args.args[0] if call_args.args else call_args.kwargs.get("url")
        assert url == "redis://localhost:6379/1"
