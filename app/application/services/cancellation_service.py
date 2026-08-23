"""Cancellation service for distributed run cancellation."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID

from app.domain.events.cancellation_events import (
    CancellationAcknowledged,
    CancellationCompleted,
    CancellationRequested,
    CancellationTimeout,
)
from app.domain.repositories.run import RunRepository
from app.infrastructure.cache.cancellation_signals import CancellationSignals
from app.infrastructure.observability.logging import get_logger

if TYPE_CHECKING:
    from app.settings import Settings

logger = get_logger(__name__)


class CancellationService:
    """Service for managing distributed cancellation of runs."""

    def __init__(
        self,
        run_repository: RunRepository,
        cancellation_signals: CancellationSignals,
        settings: Settings,
    ) -> None:
        """Initialize cancellation service.

        Args:
            run_repository: Run repository for accessing run data
            cancellation_signals: Redis-based cancellation signal system
            settings: Application settings
        """
        self._run_repository = run_repository
        self._cancellation_signals = cancellation_signals
        self._settings = settings

    async def request_cancellation(self, run_id: UUID, reason: str | None = None) -> bool:
        """Request cancellation of a run.

        Args:
            run_id: Run ID to cancel
            reason: Optional cancellation reason

        Returns:
            True if cancellation was requested successfully, False otherwise
        """
        run = await self._run_repository.get(run_id)
        if not run:
            logger.warning("Run not found for cancellation request", extra={"run_id": str(run_id)})
            return False

        if run.state.is_terminal:
            logger.info(
                "Run already in terminal state",
                extra={"run_id": str(run_id), "state": run.state.value},
            )
            return True  # Idempotent - already cancelled/completed

        # Set cancellation flag in database
        run.cancel_requested_at = datetime.now(UTC)
        await self._run_repository.update(run)

        # Emit domain event
        run.add_event(
            CancellationRequested(
                run_id=run.id,
                tenant_id=run.tenant_id,
                reason=reason,
                requested_at=datetime.now(UTC),
            )
        )

        # Publish cancellation signal via Redis
        success = await self._cancellation_signals.publish_request(
            str(run_id), str(run.tenant_id), reason
        )

        # Set polling flag as fallback
        await self._cancellation_signals.set_flag(str(run_id))

        if success:
            logger.info(
                "Cancellation requested successfully",
                extra={"run_id": str(run_id), "reason": reason},
            )
        else:
            logger.warning(
                "Cancellation requested but signal publish failed",
                extra={"run_id": str(run_id)},
            )

        return success

    async def is_cancelled(self, run_id: UUID) -> bool:
        """Check if a run has been cancelled.

        Args:
            run_id: Run ID to check

        Returns:
            True if run is cancelled, False otherwise
        """
        # Fast check via Redis flag
        if await self._cancellation_signals.check_flag(str(run_id)):
            return True

        # Fallback to database check
        run = await self._run_repository.get(run_id)
        if not run:
            return False

        return run.cancel_requested_at is not None

    async def acknowledge_cancellation(self, run_id: UUID, worker_id: str) -> bool:
        """Acknowledge cancellation request from a worker.

        Args:
            run_id: Run ID being cancelled
            worker_id: Worker ID acknowledging cancellation

        Returns:
            True if acknowledgement was successful, False otherwise
        """
        run = await self._run_repository.get(run_id)
        if not run:
            logger.warning(
                "Run not found for cancellation acknowledgement",
                extra={"run_id": str(run_id)},
            )
            return False

        # Emit domain event
        run.add_event(
            CancellationAcknowledged(
                run_id=run.id,
                tenant_id=run.tenant_id,
                worker_id=worker_id,
                acknowledged_at=datetime.now(UTC),
            )
        )

        # Publish acknowledgement signal
        success = await self._cancellation_signals.publish_acknowledgement(
            str(run_id), str(run.tenant_id), worker_id
        )

        if success:
            logger.info(
                "Cancellation acknowledged",
                extra={"run_id": str(run_id), "worker_id": worker_id},
            )

        return success

    async def complete_cancellation(
        self,
        run_id: UUID,
        worker_id: str,
        steps_cancelled: int = 0,
        cleanup_performed: bool = False,
    ) -> bool:
        """Mark cancellation as completed.

        Args:
            run_id: Run ID that was cancelled
            worker_id: Worker ID completing cancellation
            steps_cancelled: Number of steps cancelled
            cleanup_performed: Whether cleanup was performed

        Returns:
            True if completion was successful, False otherwise
        """
        run = await self._run_repository.get(run_id)
        if not run:
            logger.warning(
                "Run not found for cancellation completion",
                extra={"run_id": str(run_id)},
            )
            return False

        # Transition run to cancelled state
        run.cancel(reason="Cancellation completed")

        # Emit domain event
        run.add_event(
            CancellationCompleted(
                run_id=run.id,
                tenant_id=run.tenant_id,
                worker_id=worker_id,
                completed_at=datetime.now(UTC),
                steps_cancelled=steps_cancelled,
                cleanup_performed=cleanup_performed,
            )
        )

        await self._run_repository.update(run)

        # Publish completion signal
        success = await self._cancellation_signals.publish_completion(
            str(run_id),
            str(run.tenant_id),
            worker_id,
            steps_cancelled,
            cleanup_performed,
        )

        # Cleanup cancellation resources
        await self._cancellation_signals.cleanup(str(run_id))

        if success:
            logger.info(
                "Cancellation completed",
                extra={
                    "run_id": str(run_id),
                    "worker_id": worker_id,
                    "steps_cancelled": steps_cancelled,
                },
            )

        return success

    async def check_cancellation_timeout(self, run_id: UUID) -> bool:
        """Check if cancellation has timed out.

        Args:
            run_id: Run ID to check

        Returns:
            True if cancellation has timed out, False otherwise
        """
        run = await self._run_repository.get(run_id)
        if not run or run.cancel_requested_at is None:
            return False

        elapsed = (datetime.now(UTC) - run.cancel_requested_at).total_seconds()
        timeout = self._settings.cancellation_timeout_seconds

        if elapsed > timeout:
            # Emit timeout event
            run.add_event(
                CancellationTimeout(
                    run_id=run.id,
                    tenant_id=run.tenant_id,
                    timeout_seconds=timeout,
                    timed_out_at=datetime.now(UTC),
                )
            )
            await self._run_repository.update(run)

            logger.warning(
                "Cancellation timeout",
                extra={"run_id": str(run_id), "elapsed_seconds": elapsed, "timeout": timeout},
            )
            return True

        return False

    async def cleanup_cancellation_resources(self, run_id: UUID) -> bool:
        """Clean up cancellation resources for a run.

        Args:
            run_id: Run ID to cleanup

        Returns:
            True if cleanup was successful, False otherwise
        """
        return await self._cancellation_signals.cleanup(str(run_id))

    async def subscribe_to_cancellation(self, run_id: UUID):
        """Subscribe to cancellation signals for a run.

        Args:
            run_id: Run ID to subscribe to

        Yields:
            Cancellation signal dictionaries
        """
        async for signal in self._cancellation_signals.subscribe(str(run_id)):
            yield signal
