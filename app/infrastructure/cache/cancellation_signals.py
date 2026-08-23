"""Redis-based cancellation signals for distributed cancellation."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING

from app.infrastructure.observability.logging import get_logger

if TYPE_CHECKING:
    from redis.asyncio import Redis

logger = get_logger(__name__)


class CancellationSignals:
    """Redis pub/sub based cancellation signal system."""

    def __init__(self, redis_client: Redis[str], channel_prefix: str = "cancellation") -> None:
        """Initialize cancellation signals.

        Args:
            redis_client: Redis client instance
            channel_prefix: Prefix for cancellation channels
        """
        self._redis = redis_client
        self._channel_prefix = channel_prefix

    def _channel_name(self, run_id: str) -> str:
        """Generate Redis channel name for a run."""
        return f"{self._channel_prefix}:{run_id}"

    async def publish_request(self, run_id: str, tenant_id: str, reason: str | None = None) -> bool:
        """Publish a cancellation request for a run.

        Args:
            run_id: Run ID as string
            tenant_id: Tenant ID as string
            reason: Optional cancellation reason

        Returns:
            True if published successfully, False otherwise
        """
        channel = self._channel_name(run_id)
        from datetime import UTC, datetime

        payload = {
            "signal_type": "request",
            "run_id": run_id,
            "tenant_id": tenant_id,
            "reason": reason,
            "timestamp": datetime.now(UTC).isoformat(),
        }

        try:
            await self._redis.publish(channel, json.dumps(payload))
            logger.info(
                "Cancellation request published",
                extra={"run_id": run_id, "tenant_id": tenant_id, "reason": reason},
            )
            return True
        except Exception as e:
            logger.error(
                "Failed to publish cancellation request",
                extra={"run_id": run_id, "error": str(e)},
            )
            return False

    async def publish_acknowledgement(
        self, run_id: str, tenant_id: str, worker_id: str
    ) -> bool:
        """Publish a cancellation acknowledgement from a worker.

        Args:
            run_id: Run ID as string
            tenant_id: Tenant ID as string
            worker_id: Worker ID acknowledging cancellation

        Returns:
            True if published successfully, False otherwise
        """
        channel = self._channel_name(run_id)
        payload = {
            "signal_type": "ack",
            "run_id": run_id,
            "tenant_id": tenant_id,
            "worker_id": worker_id,
        }

        try:
            await self._redis.publish(channel, json.dumps(payload))
            logger.info(
                "Cancellation acknowledgement published",
                extra={"run_id": run_id, "worker_id": worker_id},
            )
            return True
        except Exception as e:
            logger.error(
                "Failed to publish cancellation acknowledgement",
                extra={"run_id": run_id, "worker_id": worker_id, "error": str(e)},
            )
            return False

    async def publish_completion(
        self,
        run_id: str,
        tenant_id: str,
        worker_id: str,
        steps_cancelled: int = 0,
        cleanup_performed: bool = False,
    ) -> bool:
        """Publish a cancellation completion notification.

        Args:
            run_id: Run ID as string
            tenant_id: Tenant ID as string
            worker_id: Worker ID completing cancellation
            steps_cancelled: Number of steps cancelled
            cleanup_performed: Whether cleanup was performed

        Returns:
            True if published successfully, False otherwise
        """
        channel = self._channel_name(run_id)
        payload = {
            "signal_type": "complete",
            "run_id": run_id,
            "tenant_id": tenant_id,
            "worker_id": worker_id,
            "steps_cancelled": steps_cancelled,
            "cleanup_performed": cleanup_performed,
        }

        try:
            await self._redis.publish(channel, json.dumps(payload))
            logger.info(
                "Cancellation completion published",
                extra={
                    "run_id": run_id,
                    "worker_id": worker_id,
                    "steps_cancelled": steps_cancelled,
                },
            )
            return True
        except Exception as e:
            logger.error(
                "Failed to publish cancellation completion",
                extra={"run_id": run_id, "worker_id": worker_id, "error": str(e)},
            )
            return False

    async def subscribe(self, run_id: str) -> AsyncIterator[dict]:
        """Subscribe to cancellation signals for a run.

        Args:
            run_id: Run ID as string

        Yields:
            Signal dictionaries as they are received
        """
        channel = self._channel_name(run_id)
        pubsub = self._redis.pubsub()

        try:
            await pubsub.subscribe(channel)
            logger.info(
                "Subscribed to cancellation channel",
                extra={"run_id": run_id, "channel": channel},
            )

            async for message in pubsub.listen():
                if message["type"] == "message":
                    try:
                        data = json.loads(message["data"])
                        yield data
                    except json.JSONDecodeError as e:
                        logger.error(
                            "Failed to decode cancellation signal",
                            extra={"run_id": run_id, "error": str(e)},
                        )
                        continue

        except Exception as e:
            logger.error(
                "Error in cancellation subscription",
                extra={"run_id": run_id, "error": str(e)},
            )
        finally:
            await pubsub.unsubscribe(channel)
            logger.info(
                "Unsubscribed from cancellation channel",
                extra={"run_id": run_id, "channel": channel},
            )

    async def set_flag(self, run_id: str) -> bool:
        """Set a cancellation flag in Redis for fast polling fallback.

        Args:
            run_id: Run ID as string

        Returns:
            True if flag was set successfully, False otherwise
        """
        key = f"{self._channel_prefix}:flag:{run_id}"
        try:
            await self._redis.set(key, "1", ex=300)  # 5 minute TTL
            return True
        except Exception as e:
            logger.error(
                "Failed to set cancellation flag",
                extra={"run_id": run_id, "error": str(e)},
            )
            return False

    async def check_flag(self, run_id: str) -> bool:
        """Check if cancellation flag is set.

        Args:
            run_id: Run ID as string

        Returns:
            True if cancellation flag is set, False otherwise
        """
        key = f"{self._channel_prefix}:flag:{run_id}"
        try:
            result = await self._redis.get(key)
            return result is not None
        except Exception as e:
            logger.error(
                "Failed to check cancellation flag",
                extra={"run_id": run_id, "error": str(e)},
            )
            return False

    async def clear_flag(self, run_id: str) -> bool:
        """Clear cancellation flag.

        Args:
            run_id: Run ID as string

        Returns:
            True if flag was cleared successfully, False otherwise
        """
        key = f"{self._channel_prefix}:flag:{run_id}"
        try:
            await self._redis.delete(key)
            return True
        except Exception as e:
            logger.error(
                "Failed to clear cancellation flag",
                extra={"run_id": run_id, "error": str(e)},
            )
            return False

    async def cleanup(self, run_id: str) -> bool:
        """Clean up all cancellation resources for a run.

        Args:
            run_id: Run ID as string

        Returns:
            True if cleanup was successful, False otherwise
        """
        try:
            # Clear flag
            await self.clear_flag(run_id)
            # Note: Channels are automatically cleaned up by Redis
            logger.info("Cancellation resources cleaned up", extra={"run_id": run_id})
            return True
        except Exception as e:
            logger.error(
                "Failed to cleanup cancellation resources",
                extra={"run_id": run_id, "error": str(e)},
            )
            return False

    async def health_check(self) -> bool:
        """Check if cancellation signals system is healthy.

        Returns:
            True if healthy, False otherwise
        """
        try:
            await self._redis.ping()
            return True
        except Exception as e:
            logger.error("Cancellation signals health check failed", extra={"error": str(e)})
            return False
