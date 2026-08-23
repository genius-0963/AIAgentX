"""Redis-based rate limiter using token bucket algorithm."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

from app.infrastructure.observability.logging import get_logger

if TYPE_CHECKING:
    from redis.asyncio import Redis

logger = get_logger(__name__)


class RateLimiter:
    """Redis-based rate limiter with token bucket algorithm."""

    # Lua script for atomic rate limit check and increment
    RATE_LIMIT_SCRIPT = """
local key = KEYS[1]
local limit = tonumber(ARGV[1])
local window = tonumber(ARGV[2])
local now = tonumber(ARGV[3])

-- Get current count and expiry
local current = redis.call('GET', key)
local expiry = redis.call('PTTL', key)

-- If key doesn't exist or expired, create new
if current == false or expiry < 0 then
    redis.call('SET', key, 1, 'PX', window * 1000)
    return {1, limit, now + window}
end

-- Check if limit exceeded
if tonumber(current) >= limit then
    local reset = now + (expiry / 1000)
    return {0, 0, reset}
end

-- Increment count
local new_count = redis.call('INCR', key)
return {new_count, limit - new_count, now + window}
"""

    # Lua script for concurrency control
    CONCURRENCY_SCRIPT = """
local key = KEYS[1]
local limit = tonumber(ARGV[1])
local action = ARGV[2]  -- 'check', 'increment', or 'decrement'

if action == 'check' then
    local current = tonumber(redis.call('GET', key)) or 0
    if current >= limit then
        return {0, 0}
    else
        return {1, limit - current}
    end
elseif action == 'increment' then
    local current = tonumber(redis.call('INCR', key)) or 1
    redis.call('EXPIRE', key, 3600)  -- 1 hour expiry
    local remaining = limit - current
    return {current, remaining}
elseif action == 'decrement' then
    local current = tonumber(redis.call('GET', key)) or 0
    if current > 0 then
        current = redis.call('DECR', key)
    end
    local remaining = limit - current
    return {current, remaining}
end
"""

    def __init__(self, redis_client: Redis[str]) -> None:
        """Initialize rate limiter.

        Args:
            redis_client: Redis client instance
        """
        self._redis = redis_client
        self._rate_limit_script_loaded = False
        self._concurrency_script_loaded = False

    async def _ensure_scripts_loaded(self) -> None:
        """Ensure Lua scripts are loaded into Redis."""
        if not self._rate_limit_script_loaded:
            await self._redis.script_load(self.RATE_LIMIT_SCRIPT)
            self._rate_limit_script_loaded = True

        if not self._concurrency_script_loaded:
            await self._redis.script_load(self.CONCURRENCY_SCRIPT)
            self._concurrency_script_loaded = True

    async def check_rate_limit(
        self,
        key: str,
        limit: int,
        window_seconds: int = 60,
    ) -> dict[str, Any]:
        """Check if request is within rate limit.

        Args:
            key: Rate limit key
            limit: Maximum requests allowed
            window_seconds: Time window in seconds

        Returns:
            Dictionary with 'allowed', 'remaining', and 'reset_at'
        """
        await self._ensure_scripts_loaded()

        try:
            now = int(time.time())
            result = await self._redis.evalsha(
                self._rate_limit_script_loaded,
                1,
                key,
                limit,
                window_seconds,
                now,
            )

            return {
                "allowed": result[0] > 0,
                "remaining": result[1],
                "reset_at": result[2],
            }
        except Exception as e:
            logger.error(
                "Rate limit check failed",
                extra={"key": key, "limit": limit, "error": str(e)},
            )
            # Fail open - allow request if check fails
            return {"allowed": True, "remaining": limit, "reset_at": now + window_seconds}

    async def check_concurrency(
        self,
        key: str,
        limit: int,
    ) -> dict[str, Any]:
        """Check if within concurrency limit.

        Args:
            key: Concurrency key
            limit: Maximum concurrent operations

        Returns:
            Dictionary with 'allowed' and 'remaining'
        """
        await self._ensure_scripts_loaded()

        try:
            result = await self._redis.evalsha(
                self._concurrency_script_loaded,
                1,
                key,
                limit,
                "check",
            )

            return {
                "allowed": result[0] > 0,
                "remaining": result[1],
            }
        except Exception as e:
            logger.error(
                "Concurrency check failed",
                extra={"key": key, "limit": limit, "error": str(e)},
            )
            # Fail open - allow request if check fails
            return {"allowed": True, "remaining": limit}

    async def increment_concurrency(self, key: str) -> dict[str, Any]:
        """Increment concurrency counter.

        Args:
            key: Concurrency key

        Returns:
            Dictionary with 'current' and 'remaining'
        """
        await self._ensure_scripts_loaded()

        try:
            # Use a default limit of 1000 for increment
            result = await self._redis.evalsha(
                self._concurrency_script_loaded,
                1,
                key,
                1000,
                "increment",
            )

            return {
                "current": result[0],
                "remaining": result[1],
            }
        except Exception as e:
            logger.error(
                "Concurrency increment failed",
                extra={"key": key, "error": str(e)},
            )
            return {"current": 0, "remaining": 1000}

    async def decrement_concurrency(self, key: str) -> dict[str, Any]:
        """Decrement concurrency counter.

        Args:
            key: Concurrency key

        Returns:
            Dictionary with 'current' and 'remaining'
        """
        await self._ensure_scripts_loaded()

        try:
            # Use a default limit of 1000 for decrement
            result = await self._redis.evalsha(
                self._concurrency_script_loaded,
                1,
                key,
                1000,
                "decrement",
            )

            return {
                "current": result[0],
                "remaining": result[1],
            }
        except Exception as e:
            logger.error(
                "Concurrency decrement failed",
                extra={"key": key, "error": str(e)},
            )
            return {"current": 0, "remaining": 1000}

    async def record_request(self, key: str, window_seconds: int = 60) -> bool:
        """Record a request for rate limiting.

        Args:
            key: Rate limit key
            window_seconds: Time window in seconds

        Returns:
            True if recorded successfully, False otherwise
        """
        try:
            await self._redis.incr(key)
            await self._redis.expire(key, window_seconds)
            return True
        except Exception as e:
            logger.error(
                "Failed to record request",
                extra={"key": key, "error": str(e)},
            )
            return False

    async def get_current_usage(
        self,
        key: str,
        window_seconds: int = 60,
    ) -> dict[str, Any]:
        """Get current usage for rate limit.

        Args:
            key: Rate limit key
            window_seconds: Time window in seconds

        Returns:
            Dictionary with 'remaining' and 'reset_at'
        """
        try:
            current = await self._redis.get(key)
            current_int = int(current) if current else 0

            # Default limit of 60 for usage checks
            limit = 60
            remaining = max(0, limit - current_int)
            reset_at = int(time.time()) + window_seconds

            return {
                "remaining": remaining,
                "reset_at": reset_at,
            }
        except Exception as e:
            logger.error(
                "Failed to get current usage",
                extra={"key": key, "error": str(e)},
            )
            return {"remaining": 60, "reset_at": int(time.time()) + window_seconds}

    async def health_check(self) -> bool:
        """Check if rate limiter is healthy.

        Returns:
            True if healthy, False otherwise
        """
        try:
            await self._redis.ping()
            return True
        except Exception as e:
            logger.error("Rate limiter health check failed", extra={"error": str(e)})
            return False
