"""Unit tests for memory cache."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestEphemeralMemoryCache:
    """Tests for EphemeralMemoryCache."""

    @pytest.fixture
    def mock_redis(self):
        return AsyncMock()

    @pytest.fixture
    def cache(self, mock_redis):
        from app.infrastructure.cache.memory_cache import EphemeralMemoryCache
        return EphemeralMemoryCache(redis_client=mock_redis)

    @pytest.mark.asyncio
    async def test_set_get(self, cache, mock_redis):
        mock_redis.get.return_value = '{"key": "value"}'

        await cache.set("run-123", "mykey", {"key": "value"})
        result = await cache.get("run-123", "mykey")

        assert result == {"key": "value"}
        mock_redis.setex.assert_called_once()
        mock_redis.get.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_not_found(self, cache, mock_redis):
        mock_redis.get.return_value = None

        result = await cache.get("run-123", "nonexistent")

        assert result is None

    @pytest.mark.asyncio
    async def test_delete(self, cache, mock_redis):
        mock_redis.delete.return_value = 1

        result = await cache.delete("run-123", "mykey")

        assert result is True
        mock_redis.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_exists(self, cache, mock_redis):
        mock_redis.exists.return_value = 1

        result = await cache.exists("run-123", "mykey")

        assert result is True

    @pytest.mark.asyncio
    async def test_clear_run(self, cache, mock_redis):
        # Mock scan_iter to return keys
        async def mock_scan_iter(match=None):
            yield "memory:ephemeral:run-123:key1"
            yield "memory:ephemeral:run-123:key2"

        mock_redis.scan_iter = mock_scan_iter
        mock_redis.delete.return_value = 2

        count = await cache.clear_run("run-123")

        assert count == 2

    @pytest.mark.asyncio
    async def test_get_all(self, cache, mock_redis):
        async def mock_scan_iter(match=None):
            yield "memory:ephemeral:run-123:key1"
            yield "memory:ephemeral:run-123:key2"

        mock_redis.scan_iter = mock_scan_iter
        mock_redis.get.side_effect = ['{"a": 1}', '{"b": 2}']

        result = await cache.get_all("run-123")

        assert "key1" in result
        assert "key2" in result
        assert result["key1"] == {"a": 1}
        assert result["key2"] == {"b": 2}


class TestSessionMemoryCache:
    """Tests for SessionMemoryCache."""

    @pytest.fixture
    def mock_redis(self):
        return AsyncMock()

    @pytest.fixture
    def cache(self, mock_redis):
        from app.infrastructure.cache.memory_cache import SessionMemoryCache
        return SessionMemoryCache(redis_client=mock_redis)

    @pytest.mark.asyncio
    async def test_set_get(self, cache, mock_redis):
        mock_redis.get.return_value = '{"key": "value"}'

        await cache.set("session-123", "mykey", {"key": "value"})
        result = await cache.get("session-123", "mykey")

        assert result == {"key": "value"}

    @pytest.mark.asyncio
    async def test_append_to_history(self, cache, mock_redis):
        mock_pipeline = AsyncMock()
        mock_redis.pipeline.return_value.__aenter__.return_value = mock_pipeline

        await cache.append_to_history("session-123", {"role": "user", "content": "Hello"})

        mock_pipeline.rpush.assert_called_once()
        mock_pipeline.ltrim.assert_called_once()
        mock_pipeline.expire.assert_called_once()
        mock_pipeline.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_recent_history(self, cache, mock_redis):
        mock_redis.lrange.return_value = ['{"role": "user", "content": "Hello"}']

        history = await cache.get_recent_history("session-123", limit=10)

        assert len(history) == 1
        assert history[0]["role"] == "user"

    @pytest.mark.asyncio
    async def test_get_all_history(self, cache, mock_redis):
        mock_redis.lrange.return_value = [
            '{"role": "user", "content": "Hello"}',
            '{"role": "assistant", "content": "Hi!"}',
        ]

        history = await cache.get_all_history("session-123")

        assert len(history) == 2

    @pytest.mark.asyncio
    async def test_clear_session(self, cache, mock_redis):
        async def mock_scan_iter(match=None):
            yield "memory:session:session-123:key1"
            yield "memory:session:session-123:history"

        mock_redis.scan_iter = mock_scan_iter
        mock_redis.delete.return_value = 2

        count = await cache.clear_session("session-123")

        assert count == 2

    @pytest.mark.asyncio
    async def test_extend_ttl(self, cache, mock_redis):
        async def mock_scan_iter(match=None):
            yield "memory:session:session-123:key1"
            yield "memory:session:session-123:key2"

        mock_redis.scan_iter = mock_scan_iter
        mock_redis.expire.return_value = True

        result = await cache.extend_ttl("session-123", ttl=86400)

        assert result is True
        assert mock_redis.expire.call_count == 2

    @pytest.mark.asyncio
    async def test_get_session_keys(self, cache, mock_redis):
        async def mock_scan_iter(match=None):
            yield "memory:session:session-123:key1"
            yield "memory:session:session-123:key2"
            yield "memory:session:session-123:history"  # Should be excluded

        mock_redis.scan_iter = mock_scan_iter

        keys = await cache.get_session_keys("session-123")

        assert "key1" in keys
        assert "key2" in keys
        assert "history" not in keys


class TestMemoryCacheManager:
    """Tests for MemoryCacheManager."""

    @pytest.fixture
    def mock_redis(self):
        return AsyncMock()

    @pytest.mark.asyncio
    async def test_manager_initialization(self, mock_redis):
        from app.infrastructure.cache.memory_cache import MemoryCacheManager

        manager = MemoryCacheManager(redis_client=mock_redis)

        assert manager.ephemeral is not None
        assert manager.session is not None

    @pytest.mark.asyncio
    async def test_close(self, mock_redis):
        from app.infrastructure.cache.memory_cache import MemoryCacheManager

        manager = MemoryCacheManager(redis_client=mock_redis)
        await manager.close()

        mock_redis.aclose.assert_called_once()