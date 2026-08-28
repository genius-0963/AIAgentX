"""Idempotency service for duplicate request prevention."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

from app.infrastructure.observability.logging import get_logger

if TYPE_CHECKING:
    from app.infrastructure.cache.idempotency_store import IdempotencyStore

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class IdempotencyResult:
    """Result of idempotency check."""

    is_duplicate: bool
    cached_response: dict[str, Any] | None = None
    key_exists: bool = False
    original_request_id: str | None = None


class IdempotencyService:
    """Service for managing idempotency keys and preventing duplicate requests."""

    def __init__(
        self,
        idempotency_store: IdempotencyStore,
        ttl_seconds: int = 86400,  # 24 hours default
    ) -> None:
        """Initialize idempotency service.

        Args:
            idempotency_store: Redis-based idempotency storage
            ttl_seconds: Time-to-live for idempotency keys in seconds
        """
        self._store = idempotency_store
        self._ttl = ttl_seconds

    async def check_and_store(
        self,
        key: str,
        tenant_id: UUID,
        operation: str,
        request_data: dict[str, Any] | None = None,
    ) -> IdempotencyResult:
        """Check for existing operation and store if new.

        Args:
            key: Idempotency key
            tenant_id: Tenant ID
            operation: Operation type (e.g., "create_run", "update_agent")
            request_data: Optional request data for comparison

        Returns:
            IdempotencyResult with duplicate status and cached response if exists
        """
        # Check if key exists in storage
        existing = await self._store.get(key, str(tenant_id))
        if existing:
            logger.info(
                "Duplicate request detected via idempotency key",
                extra={
                    "key": key,
                    "tenant_id": str(tenant_id),
                    "operation": operation,
                },
            )
            return IdempotencyResult(
                is_duplicate=True,
                cached_response=existing.get("response"),
                key_exists=True,
                original_request_id=existing.get("request_id"),
            )

        # Store new request
        await self._store.set(
            key=key,
            tenant_id=str(tenant_id),
            operation=operation,
            request_data=request_data,
            ttl_seconds=self._ttl,
        )

        logger.info(
            "New request stored with idempotency key",
            extra={
                "key": key,
                "tenant_id": str(tenant_id),
                "operation": operation,
            },
        )

        return IdempotencyResult(
            is_duplicate=False,
            key_exists=False,
        )

    async def get_response(self, key: str, tenant_id: UUID) -> dict[str, Any] | None:
        """Get cached response for an idempotency key.

        Args:
            key: Idempotency key
            tenant_id: Tenant ID

        Returns:
            Cached response if exists, None otherwise
        """
        existing = await self._store.get(key, str(tenant_id))
        if existing and "response" in existing:
            return existing["response"]
        return None

    async def store_response(
        self,
        key: str,
        tenant_id: UUID,
        response: dict[str, Any],
        request_id: str | None = None,
    ) -> bool:
        """Store response for an idempotency key.

        Args:
            key: Idempotency key
            tenant_id: Tenant ID
            response: Response data to cache
            request_id: Optional request ID for tracking

        Returns:
            True if stored successfully, False otherwise
        """
        # Check if key exists first
        existing = await self._store.get(key, str(tenant_id))
        if not existing:
            logger.warning(
                "Attempted to store response for non-existent idempotency key",
                extra={"key": key, "tenant_id": str(tenant_id)},
            )
            return False

        success = await self._store.set_response(
            key=key,
            tenant_id=str(tenant_id),
            response=response,
            request_id=request_id,
            ttl_seconds=self._ttl,
        )

        if success:
            logger.info(
                "Response stored for idempotency key",
                extra={
                    "key": key,
                    "tenant_id": str(tenant_id),
                    "request_id": request_id,
                },
            )

        return success

    async def expire_keys(self, tenant_id: UUID, older_than: datetime) -> int:
        """Expire idempotency keys older than specified time.

        Args:
            tenant_id: Tenant ID
            older_than: Keys older than this datetime will be expired

        Returns:
            Number of keys expired
        """
        # This would typically be called by a cleanup job
        # For now, we'll rely on Redis TTL for automatic expiration
        logger.info(
            "Idempotency key expiration check",
            extra={
                "tenant_id": str(tenant_id),
                "older_than": older_than.isoformat(),
            },
        )
        return 0

    async def invalidate_key(self, key: str, tenant_id: UUID) -> bool:
        """Invalidate an idempotency key.

        Args:
            key: Idempotency key to invalidate
            tenant_id: Tenant ID

        Returns:
            True if invalidated successfully, False otherwise
        """
        success = await self._store.delete(key, str(tenant_id))

        if success:
            logger.info(
                "Idempotency key invalidated",
                extra={"key": key, "tenant_id": str(tenant_id)},
            )

        return success

    async def health_check(self) -> bool:
        """Check if idempotency service is healthy.

        Returns:
            True if healthy, False otherwise
        """
        return await self._store.health_check()
