"""Run executor with cancellation support, memory integration, and tool security."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING
from uuid import UUID

from app.domain.entities.memory import MemoryScope
from app.domain.entities.run import Run
from app.domain.repositories.run import RunRepository
from app.domain.value_objects.state import RunStepKind
from app.infrastructure.cache.memory_cache import EphemeralMemoryCache
from app.infrastructure.observability.logging import get_logger

if TYPE_CHECKING:
    from app.application.services.cancellation_service import CancellationService
    from app.application.services.memory_write_service import MemoryWriteService
    from app.application.services.memory_retrieval_service import MemoryRetrievalService
    from app.application.services.session_memory_service import SessionMemoryService
    from app.application.services.tool_execution_service import ToolExecutionService, ToolExecutionResult
    from app.domain.services.approval_coordinator import ApprovalCoordinator

logger = get_logger(__name__)


@dataclass
class MemoryContext:
    """Memory context for run execution."""

    ephemeral: dict[str, object]
    session: list[dict]
    durable: list[dict]


class ToolApprovalRequired(Exception):
    """Exception raised when tool execution requires approval."""

    def __init__(self, approval_id: UUID) -> None:
        self.approval_id = approval_id
        super().__init__(f"Tool execution requires approval: {approval_id}")


class ToolExecutionDenied(Exception):
    """Exception raised when tool execution is denied."""

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(f"Tool execution denied: {reason}")


class RunExecutor:
    """Executor for runs with cancellation support, memory integration, and tool security."""

    def __init__(
        self,
        run_repository: RunRepository,
        cancellation_service: CancellationService,
        memory_write_service: MemoryWriteService,
        memory_retrieval_service: MemoryRetrievalService,
        session_memory_service: SessionMemoryService,
        ephemeral_cache: EphemeralMemoryCache,
        tool_execution_service: ToolExecutionService,
        approval_coordinator: ApprovalCoordinator,
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
            tool_execution_service: Tool execution service with security
            approval_coordinator: Approval coordinator for handling approvals
            worker_id: Worker ID for this executor
            check_interval: Interval in seconds to check for cancellation
        """
        self._run_repository = run_repository
        self._cancellation_service = cancellation_service
        self._memory_write_service = memory_write_service
        self._memory_retrieval_service = memory_retrieval_service
        self._session_memory_service = session_memory_service
        self._ephemeral_cache = ephemeral_cache
        self._tool_execution = tool_execution_service
        self._approvals = approval_coordinator
        self._worker_id = worker_id
        self._check_interval = check_interval

    async def execute_run(self, run_id: UUID) -> None:
        """Execute a run with cancellation support, memory integration, and tool security.

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

                # If run is awaiting approval, stop execution
                if run.state.value == "awaiting_approval":
                    logger.info("Run awaiting approval, pausing execution", extra={"run_id": str(run_id)})
                    return

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
        """Execute a single step of the run with tool security.

        Args:
            run: Run entity
        """
        # Get the next step to execute
        step = self._get_next_pending_step(run)
        if not step:
            return

        step.start()
        await self._run_repository.update_step(run.id, step)

        try:
            if step.kind == RunStepKind.TOOL_CALL:
                result = await self._execute_tool_call(run, step)
            elif step.kind == RunStepKind.APPROVAL_REQUEST:
                result = await self._handle_approval_step(run, step)
            else:
                result = await self._execute_other_step(run, step)

            step.complete(result.get("output", {}))
            
        except ToolApprovalRequired as e:
            # Run transitions to AWAITING_APPROVAL
            run.request_approval()
            step.fail(f"Approval required: {e.approval_id}")
            
        except ToolExecutionDenied as e:
            step.fail(e.reason)
            # Run may continue or fail based on configuration
            
        except Exception as e:
            step.fail(str(e))
            raise
        
        await self._run_repository.update_step(run.id, step)
        await self._run_repository.update(run)

    def _get_next_pending_step(self, run: Run) -> Run | None:
        """Get the next pending step to execute."""
        # Find the first step that hasn't been executed
        for step in run._steps:
            if step.state.value in ("queued", "running"):
                return step
        return None

    async def _execute_tool_call(self, run: Run, step: Run) -> dict[str, Any]:
        """Execute tool call with security checks."""
        tool_name = step.input_data.get("tool_name") if step.input_data else None
        action = step.input_data.get("action", "execute") if step.input_data else "execute"
        input_data = step.input_data.get("input", {}) if step.input_data else {}
        resource = step.input_data.get("resource") if step.input_data else None
        
        if not tool_name:
            raise ValueError("Tool name required for tool_call step")
        
        # Get agent version ID from run
        agent_version_id = run.agent_version_id
        
        # Execute with security
        result = await self._tool_execution.execute_tool(
            run=run,
            agent_version_id=agent_version_id,
            tool_name=tool_name,
            action=action,
            input_data=input_data,
            resource=resource,
            context={
                "run_id": str(run.id),
                "step_sequence": step.sequence,
                "tenant_id": str(run.tenant_id),
            },
        )
        
        if result.awaiting_approval:
            raise ToolApprovalRequired(approval_id=result.approval_id)
        
        if not result.success:
            raise ToolExecutionDenied(reason=result.reason)
        
        return {"output": result.output}

    async def _handle_approval_step(self, run: Run, step: Run) -> dict[str, Any]:
        """Handle explicit approval request step."""
        # This allows agents to explicitly request approval in their logic
        approval_id = step.input_data.get("approval_id") if step.input_data else None
        if not approval_id:
            raise ValueError("approval_id required for approval_request step")
        
        # Check approval status
        request = await self._approvals.get(approval_id)
        if not request:
            raise ValueError(f"Approval request {approval_id} not found")
        
        if request.state.value == "approved":
            return {"output": request.response_data or {}}
        elif request.state.value == "denied":
            raise ToolExecutionDenied(reason=request.denial_reason or "Approval denied")
        elif request.state.value == "expired":
            raise ToolExecutionDenied(reason="Approval request expired")
        else:
            # Still pending - transition run to awaiting approval
            run.request_approval()
            raise ToolApprovalRequired(approval_id=approval_id)

    async def _execute_other_step(self, run: Run, step: Run) -> dict[str, Any]:
        """Execute other step types (model_call, memory_read, etc.)."""
        # Placeholder for actual step execution
        # This would involve model calls, memory operations, etc.
        await asyncio.sleep(0.1)  # Simulate work
        return {"output": "step result"}

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
