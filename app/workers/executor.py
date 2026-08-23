"""Run executor with cancellation support and memory integration."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING
from uuid import UUID

from app.domain.entities.memory import MemoryScope
from app.domain.entities.run import Run
from app.domain.repositories.run import RunRepository
from app.infrastructure.cache.memory_cache import EphemeralMemoryCache
from app.infrastructure.observability.logging import get_logger

if TYPE_CHECKING:
    from app.application.services.cancellation_service import CancellationService
    from app.application.services.memory_write_service import MemoryWriteService
    from app.application.services.memory_retrieval_service import MemoryRetrievalService
    from app.application.services.session_memory_service import SessionMemoryService

logger = get_logger(__name__)


@dataclass
class MemoryContext:
    """Memory context for run execution."""

    ephemeral: dict[str, object]
    session: list[dict]
    durable: list[dict]


class RunExecutor:
    """Executor for runs with cancellation support and memory integration."""

    def __init__(
        self,
        run_repository: RunRepository,
        cancellation_service: CancellationService,
        memory_write_service: MemoryWriteService,
        memory_retrieval_service: MemoryRetrievalService,
        session_memory_service: SessionMemoryService,
        ephemeral_cache: EphemeralMemoryCache,
        worker_id: str,
        check_interval: float = 0.5,
    ) -> None:
        """Initialize run executor.

        Args:
            run_repository: Run repository
            cancellation_service: Cancellation service
            memory_write_service: Service for writing memory
            memory_retrieval_service: Service for retrieving memory
            session_memory_service: Service for session memory
            ephemeral_cache: Ephemeral memory cache
            worker_id: Worker ID for this executor
            check_interval: Interval in seconds to check for cancellation
        """
        self._run_repository = run_repository
        self._cancellation_service = cancellation_service
        self._memory_write_service = memory_write_service
        self._memory_retrieval_service = memory_retrieval_service
        self._session_memory_service = session_memory_service
        self._ephemeral_cache = ephemeral_cache
        self._worker_id = worker_id
        self._check_interval = check_interval

    async def execute_run(self, run_id: UUID) -> None:
        """Execute a run with cancellation support and memory integration.

        Args:
            run_id: Run ID to execute
        """
        run = await self._run_repository.get(run_id)
        if not run:
            logger.error("Run not found for execution", extra={"run_id": str(run_id)})
            return

        # Load memory context
        memory_context = await self._load_memory_context(run)
        
        # Store memory context on run for step execution
        run.memory_context = memory_context

        logger.info(
            "Starting run execution with memory",
            extra={
                "run_id": str(run_id),
                "worker_id": self._worker_id,
                "ephemeral_keys": len(memory_context.ephemeral),
                "session_messages": len(memory_context.session),
                "durable_records": len(memory_context.durable),
            },
        )

        try:
            # Start the run
            run.start(self._worker_id)
            await self._run_repository.update(run)

            # Main execution loop
            while run.can_execute():
                # Check for cancellation before each step
                if await self._cancellation_service.is_cancelled(run_id):
                    logger.info("Cancellation detected, stopping execution", extra={"run_id": str(run_id)})
                    await self._handle_cancellation(run)
                    return

                # Execute step with memory context
                await self._execute_step(run)

                # Check for cancellation after step
                if await self._cancellation_service.is_cancelled(run_id):
                    logger.info("Cancellation detected after step", extra={"run_id": str(run_id)})
                    await self._handle_cancellation(run)
                    return

            # Save ephemeral memory back to cache
            await self._save_ephemeral_memory(run)

            # Complete run successfully
            run.complete({"result": "success", "memory_ids": run.memory_written_ids})
            await self._run_repository.update(run)
            logger.info("Run completed successfully", extra={"run_id": str(run_id)})

        except Exception as e:
            logger.error("Run execution failed", extra={"run_id": str(run_id), "error": str(e)})
            run.fail(str(e))
            await self._run_repository.update(run)

    async def _load_memory_context(self, run: Run) -> MemoryContext:
        """Load memory context for a run.

        Args:
            run: Run entity

        Returns:
            Memory context with ephemeral, session, and durable memory
        """
        tenant_id = run.tenant_id
        agent_id = run.agent_version.agent_id if run.agent_version else None
        
        if not agent_id:
            return MemoryContext(ephemeral={}, session=[], durable=[])

        # Load ephemeral memory from Redis
        ephemeral = await self._ephemeral_cache.get_all(str(run.id))

        # Load session memory if session_id exists
        session = []
        if run.session_id:
            session = await self._session_memory_service.get_session_context(
                tenant_id=tenant_id,
                agent_id=agent_id,
                session_id=run.session_id,
                limit=20,
            )

        # Load relevant durable memory via semantic search
        durable = []
        if run.input_data and "query" in run.input_data:
            query = run.input_data["query"]
            if isinstance(query, str):
                durable_records = await self._memory_retrieval_service.retrieve_memory(
                    tenant_id=tenant_id,
                    agent_id=agent_id,
                    query=query,
                    namespace="conversation",
                    scope=MemoryScope.DURABLE,
                    limit=8,
                )
                durable = [
                    {
                        "id": str(r.id),
                        "content": r.content_ciphertext,
                        "metadata": r.metadata,
                        "similarity": r.metadata.get("_similarity", 0.0),
                    }
                    for r in durable_records
                ]

        return MemoryContext(ephemeral=ephemeral, session=session, durable=durable)

    async def _save_ephemeral_memory(self, run: Run) -> None:
        """Save ephemeral memory back to cache.

        Args:
            run: Run entity with updated memory context
        """
        if hasattr(run, "memory_context") and run.memory_context:
            for key, value in run.memory_context.ephemeral.items():
                await self._ephemeral_cache.set(str(run.id), key, value)

    async def write_memory_during_execution(
        self,
        run: Run,
        content: str,
        scope: MemoryScope,
        namespace: str,
        metadata: dict,
    ) -> list:
        """Write memory during run execution.

        Args:
            run: Current run entity
            content: Content to store
            scope: Memory scope
            namespace: Namespace
            metadata: Metadata

        Returns:
            List of created memory records
        """
        if not run.agent_version:
            return []

        records = await self._memory_write_service.write_memory(
            tenant_id=run.tenant_id,
            agent_id=run.agent_version.agent_id,
            content=content,
            scope=scope,
            namespace=namespace,
            metadata=metadata,
            session_id=run.session_id,
        )

        # Track written memory IDs on run
        if not hasattr(run, "memory_written_ids"):
            run.memory_written_ids = []
        run.memory_written_ids.extend([str(r.id) for r in records])

        return records

    async def _execute_step(self, run: Run) -> None:
        """Execute a single step of the run.

        Args:
            run: Run entity
        """
        # Placeholder for actual step execution
        # This would involve model calls, tool invocations, etc.
        step_sequence = len(run._steps)
        step = run.add_step(step_sequence, "model_call", {"test": "data"})
        step.start()
        await asyncio.sleep(0.1)  # Simulate work
        step.complete({"output": "step result"})
        await self._run_repository.update(run)

    async def _handle_cancellation(self, run: Run) -> None:
        """Handle cancellation of a run.

        Args:
            run: Run entity being cancelled
        """
        # Acknowledge cancellation
        await self._cancellation_service.acknowledge_cancellation(run.id, self._worker_id)

        # Perform cleanup
        steps_cancelled = len(run._steps)
        cleanup_performed = await self._perform_cleanup(run)

        # Complete cancellation
        await self._cancellation_service.complete_cancellation(
            run.id, self._worker_id, steps_cancelled, cleanup_performed
        )

        logger.info(
            "Cancellation handled",
            extra={
                "run_id": str(run.id),
                "steps_cancelled": steps_cancelled,
                "cleanup_performed": cleanup_performed,
            },
        )

    async def _perform_cleanup(self, run: Run) -> bool:
        """Perform cleanup for a cancelled run.

        Args:
            run: Run entity being cancelled

        Returns:
            True if cleanup was performed, False otherwise
        """
        # Placeholder for actual cleanup logic
        # This might include closing connections, cleaning temporary files, etc.
        logger.info("Performing cleanup for cancelled run", extra={"run_id": str(run.id)})
        return True

    async def check_cancellation_periodically(self, run_id: UUID) -> bool:
        """Periodically check for cancellation during long-running operations.

        Args:
            run_id: Run ID to check

        Returns:
            True if cancelled, False otherwise
        """
        while True:
            if await self._cancellation_service.is_cancelled(run_id):
                return True
            await asyncio.sleep(self._check_interval)
