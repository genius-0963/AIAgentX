"""Redis-based rate limiter implementation."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

import redis.asyncio as redis
from redis.asyncio import Redis


class RedisRateLimiter:
    """Redis-based rate limiter with sliding window."""

    def __init__(self, redis_client: Redis) -> None:
        self._redis = redis_client

    async def check_limit(self, key: str, limit: int, window: str) -> bool:
        """Check if rate limit is exceeded. Returns True if allowed."""
        current = await self._get_current_count(key, window)
        return current < limit

    async def increment(self, key: str, window: str) -> int:
        """Increment counter and return current count."""
        window_seconds = self._window_to_seconds(window)
        now = datetime.now()
        window_start = self._get_window_start(now, window_seconds)

        # Use a sliding window with multiple keys
        pipeline = self._redis.pipeline()

        # Current window key
        current_key = f"ratelimit:{key}:{window_start.isoformat()}"
        pipeline.incr(current_key)
        pipeline.expire(current_key, window_seconds * 2)

        # Previous window key for sliding window
        prev_window_start = window_start - timedelta(seconds=window_seconds)
        prev_key = f"ratelimit:{key}:{prev_window_start.isoformat()}"
        pipeline.get(prev_key)

        results = await pipeline.execute()
        current_count = results[0]
        prev_count = int(results[2]) if results[2] else 0

        # Calculate weighted count for sliding window
        now_ts = now.timestamp()
        window_start_ts = window_start.timestamp()
        weight = (now_ts - window_start_ts) / window_seconds

        weighted_count = current_count + int(prev_count * (1 - weight))

        return weighted_count

    async def _get_current_count(self, key: str, window: str) -> int:
        """Get current count for rate limit check."""
        window_seconds = self._window_to_seconds(window)
        now = datetime.now()
        window_start = self._get_window_start(now, window_seconds)

        current_key = f"ratelimit:{key}:{window_start.isoformat()}"
        prev_window_start = window_start - timedelta(seconds=window_seconds)
        prev_key = f"ratelimit:{key}:{prev_window_start.isoformat()}"

        pipeline = self._redis.pipeline()
        pipeline.get(current_key)
        pipeline.get(prev_key)
        results = await pipeline.execute()

        current_count = int(results[0]) if results[0] else 0
        prev_count = int(results[1]) if results[1] else 0

        now_ts = now.timestamp()
        window_start_ts = window_start.timestamp()
        weight = (now_ts - window_start_ts) / window_seconds

        return current_count + int(prev_count * (1 - weight))

    def _window_to_seconds(self, window: str) -> int:
        """Convert window string to seconds."""
        if window == "minute":
            return 60
        elif window == "hour":
            return 3600
        elif window == "day":
            return 86400
        else:
            return 60  # default to minute

    def _get_window_start(self, now: datetime, window_seconds: int) -> datetime:
        """Get the start of the current window."""
        timestamp = int(now.timestamp())
        window_start_ts = (timestamp // window_seconds) * window_seconds
        return datetime.fromtimestamp(window_start_ts, tz=now.tzinfo)