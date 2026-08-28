"""Outbox flusher worker for reliable audit event delivery."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import TYPE_CHECKING, Any

import dramatiq
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.db.engine import get_session_factory
from app.infrastructure.db.models.outbox import OutboxEventModel
from app.settings import Settings, get_settings

if TYPE_CHECKING:
    from app.settings import Settings

logger = logging.getLogger(__name__)


@dramatiq.actor(
    max_retries=3,
    min_backoff=1000,
    max_backoff=10000,
    time_limit=30000,
)
def flush_audit_outbox(settings_dict: dict[str, Any] | None = None) -> int:
    """Flush unprocessed audit outbox events.

    This worker processes audit outbox events and delivers them to
    the audit log storage. It runs periodically to ensure reliable
    delivery of audit events.

    Args:
        settings_dict: Application settings as dict (injected by dramatiq or uses defaults).

    Returns:
        Number of events processed.
    """
    import asyncio

    return asyncio.run(_flush_audit_outbox_async(settings_dict))


async def _flush_audit_outbox_async(settings_dict: dict[str, Any] | None = None) -> int:
    """Async implementation of outbox flush.

    Args:
        settings_dict: Application settings as dict.

    Returns:
        Number of events processed.
    """
    settings = Settings(**settings_dict) if settings_dict else get_settings()

    if not settings.audit_enabled:
        logger.debug("Audit is disabled, skipping outbox flush")
        return 0

    session_factory = get_session_factory(settings)
    processed_count = 0

    async with session_factory() as session:
        # Get unprocessed audit outbox events
        stmt = select(OutboxEventModel).where(
            OutboxEventModel.event_type == "audit_log",
            OutboxEventModel.processed_at.is_(None),
        ).limit(settings.audit_batch_size)

        result = await session.execute(stmt)
        events = result.scalars().all()

        for event in events:
            try:
                # Process the audit event
                await _process_audit_event(session, event)

                # Mark as processed
                event.processed_at = datetime.utcnow()
                event.updated_at = datetime.utcnow()

                await session.flush()
                processed_count += 1

            except Exception as e:  # noqa: BLE001
                logger.error(
                    "Failed to process audit outbox event %s: %s",
                    event.id,
                    e,
                )
                event.retry_count += 1
                event.last_error = str(e)
                event.updated_at = datetime.utcnow()
                await session.flush()

        await session.commit()

    if processed_count > 0:
        logger.info("Processed %d audit outbox events", processed_count)

    return processed_count


async def _process_audit_event(session: AsyncSession, event: OutboxEventModel) -> None:
    """Process a single audit outbox event.

    Args:
        session: Database session.
        event: Outbox event to process.
    """
    # The audit entry is already stored in the audit_logs table
    # This function could be extended to forward to external systems
    # (e.g., SIEM, Kafka, etc.) for tamper-proof storage

    # For now, we just mark it as processed since the audit log
    # entry was already written in the same transaction
    pass


# Periodic task configuration
async def schedule_outbox_flush(settings: Settings | None = None) -> None:
    """Schedule periodic outbox flush.

    Args:
        settings: Application settings.
    """
    if settings is None:
        settings = get_settings()

    if not settings.audit_enabled:
        return

    while True:
        await asyncio.sleep(settings.audit_flush_interval_seconds)
        try:
            flush_audit_outbox.send(settings.model_dump())
        except Exception as e:  # noqa: BLE001
            logger.error("Failed to schedule outbox flush: %s", e)


# For running as a standalone worker
async def run_outbox_flusher() -> None:
    """Run the outbox flusher continuously."""
    settings = get_settings()

    if not settings.audit_enabled:
        logger.info("Audit is disabled, outbox flusher not started")
        return

    logger.info(
        "Starting audit outbox flusher",
        extra={
            "batch_size": settings.audit_batch_size,
            "flush_interval_seconds": settings.audit_flush_interval_seconds,
        },
    )

    while True:
        await asyncio.sleep(settings.audit_flush_interval_seconds)
        try:
            await _flush_audit_outbox_async(settings.model_dump())
        except Exception as e:  # noqa: BLE001
            logger.error("Outbox flush error: %s", e)