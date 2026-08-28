"""Tool execution service with security enforcement."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from app.domain.entities.approval_request import ApprovalType
from app.domain.entities.run import Run
from app.domain.entities.tool_grant import ToolGrant
from app.domain.repositories.approval import ApprovalRequestRepository
from app.domain.repositories.tool_grant import ToolGrantRepository
from app.domain.services.approval_coordinator import ApprovalCoordinator
from app.domain.services.policy_evaluator import PolicyDecision, PolicyEvaluator
from app.domain.value_objects.policy import ToolPolicy


@dataclass(frozen=True, slots=True)
class ToolExecutionResult:
    """Result of tool execution."""
    success: bool
    output: dict[str, Any] | None = None
    reason: str = ""
    awaiting_approval: bool = False
    approval_id: UUID | None = None
    rate_limit_info: Any | None = None

    @classmethod
    def allowed(cls, output: dict[str, Any]) -> ToolExecutionResult:
        return cls(success=True, output=output)

    @classmethod
    def denied(cls, reason: str) -> ToolExecutionResult:
        return cls(success=False, reason=reason)

    @classmethod
    def awaiting_approval(cls, approval_id: UUID) -> ToolExecutionResult:
        return cls(success=False, awaiting_approval=True, approval_id=approval_id, reason="Awaiting approval")

    @classmethod
    def rate_limited(cls, rate_limit_info: Any) -> ToolExecutionResult:
        return cls(success=False, reason="Rate limit exceeded", rate_limit_info=rate_limit_info)


class RateLimiter:
    """Rate limiter interface."""

    async def check_limit(self, key: str, limit: int, window: str) -> bool:
        """Check if rate limit is exceeded. Returns True if allowed."""
        raise NotImplementedError

    async def increment(self, key: str, window: str) -> int:
        """Increment counter and return current count."""
        raise NotImplementedError


class ToolExecutionService:
    """Service for secure tool execution with policy enforcement."""

    def __init__(
        self,
        tool_grant_repo: ToolGrantRepository,
        approval_coordinator: ApprovalCoordinator,
        rate_limiter: RateLimiter,
    ) -> None:
        self._grants = tool_grant_repo
        self._approvals = approval_coordinator
        self._rate_limiter = rate_limiter

    async def execute_tool(
        self,
        run: Run,
        agent_version_id: UUID,
        tool_name: str,
        action: str,
        input_data: dict[str, Any],
        resource: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> ToolExecutionResult:
        """Execute tool with security checks."""
        # 1. Get tool grant
        grant = await self._grants.get_by_tool(agent_version_id, tool_name)
        if not grant:
            return ToolExecutionResult.denied("No grant found for tool")

        # 2. Evaluate policy
        decision = grant.evaluate(action, resource, context)

        # 3. Check rate limits
        if decision.rate_limit:
            allowed = await self._rate_limiter.check_limit(
                key=f"tool:{tool_name}:{action}:{run.tenant_id}",
                limit=decision.rate_limit.limit,
                window=decision.rate_limit.scope,
            )
            if not allowed:
                return ToolExecutionResult.rate_limited(decision.rate_limit)

        # 4. Handle approval requirement
        if decision.requires_approval:
            request = await self._approvals.request_approval(
                run_id=run.id,
                step_sequence=len(run.steps) if hasattr(run, 'steps') else 0,
                tool_name=tool_name,
                action=action,
                resource=resource,
                input_data=input_data,
                policy_reason=decision.reason,
                requested_by="executor",
                approval_type=ApprovalType.TOOL_EXECUTION,
            )

            # Transition run to awaiting approval
            run.request_approval()

            return ToolExecutionResult.awaiting_approval(request.id)

        # 5. Execute tool (delegated to actual tool handler)
        result = await self._execute_tool_handler(tool_name, action, input_data)

        # 6. Increment rate limit counter if applicable
        if decision.rate_limit:
            await self._rate_limiter.increment(
                key=f"tool:{tool_name}:{action}:{run.tenant_id}",
                window=decision.rate_limit.scope,
            )

        return result

    async def _execute_tool_handler(
        self,
        tool_name: str,
        action: str,
        input_data: dict[str, Any],
    ) -> ToolExecutionResult:
        """Delegate to actual tool implementation."""
        # This integrates with existing tool registry
        # For now, return a mock success result
        return ToolExecutionResult.allowed({"result": "success", "tool": tool_name, "action": action})