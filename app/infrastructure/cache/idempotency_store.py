"""Redis-based idempotency key storage."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from app.infrastructure.observability.logging import get_logger

if TYPE_CHECKING:
    from redis.asyncio import Redis

logger = get_logger(__name__)


class IdempotencyStore:
    """Redis-based storage for idempotency keys."""

    def __init__(self, redis_client: Redis[str], key_prefix: str = "idempotency") -> None:
        """Initialize idempotency store.

        Args:
            redis_client: Redis client instance
            key_prefix: Prefix for idempotency keys
        """
        self._redis = redis_client
        self._key_prefix = key_prefix

    def _make_key(self, key: str, tenant_id: str) -> str:
        """Generate Redis key for idempotency storage."""
        return f"{self._key_prefix}:{tenant_id}:{key}"

    async def get(self, key: str, tenant_id: str) -> dict[str, Any] | None:
        """Get idempotency data for a key.

        Args:
            key: Idempotency key
            tenant_id: Tenant ID as string

        Returns:
            Dictionary with idempotency data or None if not found
        """
        redis_key = self._make_key(key, tenant_id)
        try:
            data = await self._redis.get(redis_key)
            if not data:
                return None

            return json.loads(data)
        except Exception as e:
            logger.error(
                "Failed to get idempotency data",
                extra={"key": key, "tenant_id": tenant_id, "error": str(e)},
            )
            return None

    async def set(
        self,
        key: str,
        tenant_id: str,
        operation: str,
        request_data: dict[str, Any] | None = None,
        ttl_seconds: int = 86400,
    ) -> bool:
        """Store new idempotency key.

        Args:
            key: Idempotency key
            tenant_id: Tenant ID as string
            operation: Operation type
            request_data: Optional request data
            ttl_seconds: Time-to-live in seconds

        Returns:
            True if stored successfully, False otherwise
        """
        redis_key = self._make_key(key, tenant_id)
        from datetime import UTC, datetime

        data = {
            "key": key,
            "tenant_id": tenant_id,
            "operation": operation,
            "request_data": request_data,
            "created_at": datetime.now(UTC).isoformat(),
            "response": None,  # Response will be set later
            "request_id": None,
        }

        try:
            await self._redis.set(redis_key, json.dumps(data), ex=ttl_seconds)
            return True
        except Exception as e:
            logger.error(
                "Failed to set idempotency data",
                extra={"key": key, "tenant_id": tenant_id, "error": str(e)},
            )
            return False

    async def set_response(
        self,
        key: str,
        tenant_id: str,
        response: dict[str, Any],
        request_id: str | None = None,
        ttl_seconds: int = 86400,
    ) -> bool:
        """Update idempotency key with response.

        Args:
            key: Idempotency key
            tenant_id: Tenant ID as string
            response: Response data to store
            request_id: Optional request ID
            ttl_seconds: Time-to-live in seconds

        Returns:
            True if updated successfully, False otherwise
        """
        redis_key = self._make_key(key, tenant_id)

        try:
            # Get existing data
            existing_data = await self.get(key, tenant_id)
            if not existing_data:
                logger.warning(
                    "Attempted to set response for non-existent idempotency key",
                    extra={"key": key, "tenant_id": tenant_id},
                )
                return False

            # Update with response
            existing_data["response"] = response
            existing_data["request_id"] = request_id
            from datetime import UTC, datetime

            existing_data["completed_at"] = datetime.now(UTC).isoformat()

            # Store updated data
            await self._redis.set(redis_key, json.dumps(existing_data), ex=ttl_seconds)
            return True
        except Exception as e:
            logger.error(
                "Failed to set idempotency response",
                extra={"key": key, "tenant_id": tenant_id, "error": str(e)},
            )
            return False

    async def delete(self, key: str, tenant_id: str) -> bool:
        """Delete idempotency key.

        Args:
            key: Idempotency key to delete
            tenant_id: Tenant ID as string

        Returns:
            True if deleted successfully, False otherwise
        """
        redis_key = self._make_key(key, tenant_id)
        try:
            await self._redis.delete(redis_key)
            return True
        except Exception as e:
            logger.error(
                "Failed to delete idempotency key",
                extra={"key": key, "tenant_id": tenant_id, "error": str(e)},
            )
            return False

    async def exists(self, key: str, tenant_id: str) -> bool:
        """Check if idempotency key exists.

        Args:
            key: Idempotency key to check
            tenant_id: Tenant ID as string

        Returns:
            True if key exists, False otherwise
        """
        redis_key = self._make_key(key, tenant_id)
        try:
            return bool(await self._redis.exists(redis_key))
        except Exception as e:
            logger.error(
                "Failed to check idempotency key existence",
                extra={"key": key, "tenant_id": tenant_id, "error": str(e)},
            )
            return False

    async def expire_by_pattern(self, pattern: str) -> int:
        """Expire keys matching a pattern (for cleanup).

        Args:
            pattern: Redis key pattern to match

        Returns:
            Number of keys expired
        """
        try:
            keys = []
            async for key in self._redis.scan_iter(match=pattern):
                keys.append(key)

            if keys:
                await self._redis.delete(*keys)

            return len(keys)
        except Exception as e:
            logger.error(
                "Failed to expire keys by pattern",
                extra={"pattern": pattern, "error": str(e)},
            )
            return 0

    async def health_check(self) -> bool:
        """Check if idempotency store is healthy.

        Returns:
            True if healthy, False otherwise
        """
        try:
            await self._redis.ping()
            return True
        except Exception as e:
            logger.error("Idempotency store health check failed", extra={"error": str(e)})
            return False
