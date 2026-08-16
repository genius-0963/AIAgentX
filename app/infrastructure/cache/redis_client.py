"""Async Redis client factory and health check.

This is the only module that imports the ``redis`` library directly; the
application layer depends on the abstract ``Cache`` port.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Protocol

from redis import asyncio as aioredis

if TYPE_CHECKING:
    from app.settings import Settings

logger = logging.getLogger(__name__)


class Cache(Protocol):
    """Abstract cache port implemented by the Redis client."""

    async def ping(self) -> bool: ...
    async def get(self, key: str) -> str | None: ...
    async def set(self, key: str, value: str, ex: int | None = None) -> bool | None: ...
    async def delete(self, key: str) -> int: ...
    async def aclose(self) -> None: ...


def create_redis_client(settings: Settings) -> aioredis.Redis[str]:
    """Create a configured async Redis client from application settings."""
    return aioredis.from_url(
        settings.redis_url,
        max_connections=settings.redis_pool_max_connections,
        socket_timeout=settings.redis_socket_timeout,
        socket_connect_timeout=settings.redis_socket_timeout,
        decode_responses=True,
        health_check_interval=30,
    )


async def check_redis_health(client: aioredis.Redis[str]) -> bool:
    """Return True if Redis responds to PING."""
    try:
        return bool(await client.ping())
    except Exception as exc:  # noqa: BLE001
        logger.warning("Redis health check failed: %s", exc)
        return False
