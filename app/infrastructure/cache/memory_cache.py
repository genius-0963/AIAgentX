"""Redis-based memory cache for ephemeral and session memory."""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING
from uuid import UUID

import redis.asyncio as redis

from app.settings import get_settings

if TYPE_CHECKING:
    from app.infrastructure.observability.logging import get_logger

logger = logging.getLogger(__name__)


class EphemeralMemoryCache:
    """Redis cache for ephemeral (per-run) memory."""

    KEY_PREFIX = "memory:ephemeral"
    DEFAULT_TTL = 86400  # 24 hours in seconds

    def __init__(
        self,
        redis_client: redis.Redis | None = None,
        default_ttl: int = DEFAULT_TTL,
    ) -> None:
        """Initialize ephemeral memory cache.

        Args:
            redis_client: Redis client instance
            default_ttl: Default TTL in seconds
        """
        self._redis = redis_client
        self._default_ttl = default_ttl
        self._settings = get_settings()

    async def _get_redis(self) -> redis.Redis:
        """Get or create Redis client."""
        if self._redis is None:
            self._redis = redis.from_url(
                self._settings.redis_url,
                encoding="utf-8",
                decode_responses=True,
            )
        return self._redis

    def _make_key(self, run_id: str, key: str) -> str:
        """Create Redis key for ephemeral memory."""
        return f"{self.KEY_PREFIX}:{run_id}:{key}"

    async def set(
        self,
        run_id: str,
        key: str,
        value: object,
        ttl: int | None = None,
    ) -> bool:
        """Set a value in ephemeral memory.

        Args:
            run_id: The run ID
            key: The memory key
            value: The value to store (will be JSON serialized)
            ttl: TTL in seconds (defaults to default_ttl)

        Returns:
            True if successful
        """
        try:
            r = await self._get_redis()
            redis_key = self._make_key(run_id, key)
            serialized = json.dumps(value, default=str)
            await r.setex(redis_key, ttl or self._default_ttl, serialized)
            return True
        except Exception as e:
            logger.error(f"Failed to set ephemeral memory: {e}", extra={"run_id": run_id, "key": key})
            return False

    async def get(self, run_id: str, key: str) -> object | None:
        """Get a value from ephemeral memory.

        Args:
            run_id: The run ID
            key: The memory key

        Returns:
            The deserialized value or None if not found
        """
        try:
            r = await self._get_redis()
            redis_key = self._make_key(run_id, key)
            value = await r.get(redis_key)
            if value is None:
                return None
            return json.loads(value)
        except Exception as e:
            logger.error(f"Failed to get ephemeral memory: {e}", extra={"run_id": run_id, "key": key})
            return None

    async def delete(self, run_id: str, key: str) -> bool:
        """Delete a key from ephemeral memory.

        Args:
            run_id: The run ID
            key: The memory key

        Returns:
            True if key was deleted
        """
        try:
            r = await self._get_redis()
            redis_key = self._make_key(run_id, key)
            result = await r.delete(redis_key)
            return result > 0
        except Exception as e:
            logger.error(f"Failed to delete ephemeral memory: {e}", extra={"run_id": run_id, "key": key})
            return False

    async def exists(self, run_id: str, key: str) -> bool:
        """Check if a key exists in ephemeral memory.

        Args:
            run_id: The run ID
            key: The memory key

        Returns:
            True if key exists
        """
        try:
            r = await self._get_redis()
            redis_key = self._make_key(run_id, key)
            return await r.exists(redis_key) > 0
        except Exception as e:
            logger.error(f"Failed to check ephemeral memory: {e}", extra={"run_id": run_id, "key": key})
            return False

    async def clear_run(self, run_id: str) -> int:
        """Clear all ephemeral memory for a run.

        Args:
            run_id: The run ID

        Returns:
            Number of keys deleted
        """
        try:
            r = await self._get_redis()
            pattern = f"{self.KEY_PREFIX}:{run_id}:*"
            keys = []
            async for key in r.scan_iter(match=pattern):
                keys.append(key)
            if keys:
                return await r.delete(*keys)
            return 0
        except Exception as e:
            logger.error(f"Failed to clear ephemeral memory for run: {e}", extra={"run_id": run_id})
            return 0

    async def get_all(self, run_id: str) -> dict[str, object]:
        """Get all ephemeral memory for a run.

        Args:
            run_id: The run ID

        Returns:
            Dictionary of all key-value pairs
        """
        try:
            r = await self._get_redis()
            pattern = f"{self.KEY_PREFIX}:{run_id}:*"
            result = {}
            async for key in r.scan_iter(match=pattern):
                value = await r.get(key)
                if value is not None:
                    short_key = key.replace(f"{self.KEY_PREFIX}:{run_id}:", "")
                    result[short_key] = json.loads(value)
            return result
        except Exception as e:
            logger.error(f"Failed to get all ephemeral memory: {e}", extra={"run_id": run_id})
            return {}


class SessionMemoryCache:
    """Redis cache for session memory (cross-run persistence)."""

    KEY_PREFIX = "memory:session"
    DEFAULT_TTL = 604800  # 7 days in seconds

    def __init__(
        self,
        redis_client: redis.Redis | None = None,
        default_ttl: int = DEFAULT_TTL,
    ) -> None:
        """Initialize session memory cache.

        Args:
            redis_client: Redis client instance
            default_ttl: Default TTL in seconds
        """
        self._redis = redis_client
        self._default_ttl = default_ttl
        self._settings = get_settings()

    async def _get_redis(self) -> redis.Redis:
        """Get or create Redis client."""
        if self._redis is None:
            self._redis = redis.from_url(
                self._settings.redis_url,
                encoding="utf-8",
                decode_responses=True,
            )
        return self._redis

    def _make_key(self, session_id: str, key: str) -> str:
        """Create Redis key for session memory."""
        return f"{self.KEY_PREFIX}:{session_id}:{key}"

    def _make_list_key(self, session_id: str) -> str:
        """Create Redis key for session conversation list."""
        return f"{self.KEY_PREFIX}:{session_id}:history"

    async def set(
        self,
        session_id: str,
        key: str,
        value: object,
        ttl: int | None = None,
    ) -> bool:
        """Set a value in session memory.

        Args:
            session_id: The session ID
            key: The memory key
            value: The value to store (will be JSON serialized)
            ttl: TTL in seconds (defaults to default_ttl)

        Returns:
            True if successful
        """
        try:
            r = await self._get_redis()
            redis_key = self._make_key(session_id, key)
            serialized = json.dumps(value, default=str)
            await r.setex(redis_key, ttl or self._default_ttl, serialized)
            return True
        except Exception as e:
            logger.error(f"Failed to set session memory: {e}", extra={"session_id": session_id, "key": key})
            return False

    async def get(self, session_id: str, key: str) -> object | None:
        """Get a value from session memory.

        Args:
            session_id: The session ID
            key: The memory key

        Returns:
            The deserialized value or None if not found
        """
        try:
            r = await self._get_redis()
            redis_key = self._make_key(session_id, key)
            value = await r.get(redis_key)
            if value is None:
                return None
            return json.loads(value)
        except Exception as e:
            logger.error(f"Failed to get session memory: {e}", extra={"session_id": session_id, "key": key})
            return None

    async def delete(self, session_id: str, key: str) -> bool:
        """Delete a key from session memory.

        Args:
            session_id: The session ID
            key: The memory key

        Returns:
            True if key was deleted
        """
        try:
            r = await self._get_redis()
            redis_key = self._make_key(session_id, key)
            result = await r.delete(redis_key)
            return result > 0
        except Exception as e:
            logger.error(f"Failed to delete session memory: {e}", extra={"session_id": session_id, "key": key})
            return False

    async def append_to_history(
        self,
        session_id: str,
        entry: dict,
        max_entries: int = 100,
        ttl: int | None = None,
    ) -> bool:
        """Append an entry to session conversation history.

        Args:
            session_id: The session ID
            entry: The conversation entry to append
            max_entries: Maximum entries to keep
            ttl: TTL in seconds for the history list

        Returns:
            True if successful
        """
        try:
            r = await self._get_redis()
            list_key = self._make_list_key(session_id)
            serialized = json.dumps(entry, default=str)

            # Use pipeline for atomic operations
            async with r.pipeline(transaction=True) as pipe:
                pipe.rpush(list_key, serialized)
                pipe.ltrim(list_key, -max_entries, -1)
                pipe.expire(list_key, ttl or self._default_ttl)
                await pipe.execute()

            return True
        except Exception as e:
            logger.error(f"Failed to append to session history: {e}", extra={"session_id": session_id})
            return False

    async def get_recent_history(
        self,
        session_id: str,
        limit: int = 10,
    ) -> list[dict]:
        """Get recent conversation history for a session.

        Args:
            session_id: The session ID
            limit: Maximum number of entries to return

        Returns:
            List of recent conversation entries
        """
        try:
            r = await self._get_redis()
            list_key = self._make_list_key(session_id)
            entries = await r.lrange(list_key, -limit, -1)
            return [json.loads(e) for e in entries]
        except Exception as e:
            logger.error(f"Failed to get session history: {e}", extra={"session_id": session_id})
            return []

    async def get_all_history(self, session_id: str) -> list[dict]:
        """Get full conversation history for a session.

        Args:
            session_id: The session ID

        Returns:
            List of all conversation entries
        """
        try:
            r = await self._get_redis()
            list_key = self._make_list_key(session_id)
            entries = await r.lrange(list_key, 0, -1)
            return [json.loads(e) for e in entries]
        except Exception as e:
            logger.error(f"Failed to get all session history: {e}", extra={"session_id": session_id})
            return []

    async def clear_session(self, session_id: str) -> int:
        """Clear all memory for a session.

        Args:
            session_id: The session ID

        Returns:
            Number of keys deleted
        """
        try:
            r = await self._get_redis()
            pattern = f"{self.KEY_PREFIX}:{session_id}:*"
            keys = []
            async for key in r.scan_iter(match=pattern):
                keys.append(key)
            if keys:
                return await r.delete(*keys)
            return 0
        except Exception as e:
            logger.error(f"Failed to clear session memory: {e}", extra={"session_id": session_id})
            return 0

    async def extend_ttl(self, session_id: str, ttl: int | None = None) -> bool:
        """Extend TTL for all session keys.

        Args:
            session_id: The session ID
            ttl: New TTL in seconds

        Returns:
            True if successful
        """
        try:
            r = await self._get_redis()
            pattern = f"{self.KEY_PREFIX}:{session_id}:*"
            new_ttl = ttl or self._default_ttl
            count = 0
            async for key in r.scan_iter(match=pattern):
                await r.expire(key, new_ttl)
                count += 1
            return count > 0
        except Exception as e:
            logger.error(f"Failed to extend session TTL: {e}", extra={"session_id": session_id})
            return False

    async def get_session_keys(self, session_id: str) -> list[str]:
        """Get all keys for a session.

        Args:
            session_id: The session ID

        Returns:
            List of memory keys (without prefix)
        """
        try:
            r = await self._get_redis()
            pattern = f"{self.KEY_PREFIX}:{session_id}:*"
            keys = []
            prefix_len = len(f"{self.KEY_PREFIX}:{session_id}:")
            async for key in r.scan_iter(match=pattern):
                if key != self._make_list_key(session_id):
                    keys.append(key[prefix_len:])
            return keys
        except Exception as e:
            logger.error(f"Failed to get session keys: {e}", extra={"session_id": session_id})
            return []


class MemoryCacheManager:
    """Unified manager for both ephemeral and session memory caches."""

    def __init__(
        self,
        redis_client: redis.Redis | None = None,
        ephemeral_ttl: int = EphemeralMemoryCache.DEFAULT_TTL,
        session_ttl: int = SessionMemoryCache.DEFAULT_TTL,
    ) -> None:
        """Initialize memory cache manager.

        Args:
            redis_client: Redis client instance
            ephemeral_ttl: TTL for ephemeral memory
            session_ttl: TTL for session memory
        """
        self.ephemeral = EphemeralMemoryCache(redis_client, ephemeral_ttl)
        self.session = SessionMemoryCache(redis_client, session_ttl)

    async def close(self) -> None:
        """Close Redis connections."""
        if self.ephemeral._redis:
            await self.ephemeral._redis.close()
        if self.session._redis and self.session._redis != self.ephemeral._redis:
            await self.session._redis.close()