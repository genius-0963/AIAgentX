"""Run management API endpoints."""

from __future__ import annotations

import re
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Header, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.errors.exceptions import ValidationError
from app.api.v1.schemas.runs import RunCreate, RunResponse, RunStatusResponse
from app.application.use_cases.run import RunUseCases
from app.infrastructure.auth.middleware import (
    AuthContext,
    get_current_tenant,
    require_scopes,
)
from app.infrastructure.db.repositories.run import SQLRunRepository
from app.infrastructure.db.session import get_session

# Main runs router for individual run operations
router = APIRouter(prefix="/runs", tags=["runs"])

# Agent-specific runs router for creation
agent_runs_router = APIRouter(tags=["agent runs"])


async def get_run_use_cases(
    session: AsyncSession = Depends(get_session),
) -> RunUseCases:
    """Dependency to get run use cases."""
    repository = SQLRunRepository(session)
    return RunUseCases(repository)


def validate_idempotency_key(key: str | None) -> str:
    """Validate idempotency key format.

    Args:
        key: Idempotency key to validate

    Returns:
        Validated idempotency key

    Raises:
        ValidationError: If key format is invalid
    """
    if not key:
        raise ValidationError(
            message="Idempotency-Key header is required",
            field="Idempotency-Key",
        )

    # Check if it's a UUID
    uuid_pattern = re.compile(
        r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
        re.IGNORECASE,
    )
    if uuid_pattern.match(key):
        return key

    # Check if it's an opaque string (32-128 characters)
    if 32 <= len(key) <= 128 and re.match(r"^[a-zA-Z0-9_-]+$", key):
        return key

    raise ValidationError(
        message="Idempotency-Key must be a UUID or 32-128 character opaque string",
        field="Idempotency-Key",
    )


@agent_runs_router.post(
    "",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=RunResponse,
    summary="Create run",
    description="Create a new run for an agent with idempotency guarantees.",
)
async def create_run(
    agent_id: UUID,
    run_data: RunCreate,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    auth: AuthContext = Depends(require_scopes("runs:write")),
    tenant_id: UUID = Depends(get_current_tenant),
    use_cases: RunUseCases = Depends(get_run_use_cases),
) -> dict[str, Any]:
    """Create a new run for an agent.

    Creates a new run with the specified input and limits. The idempotency
    key ensures that duplicate requests don't create duplicate runs.

    Requires `runs:write` scope. The agent version must be published.

    Returns 202 Accepted with run ID and events URL.
    """
    # Validate idempotency key
    validated_key = validate_idempotency_key(idempotency_key)

    # Create the run
    run = await use_cases.create_run(
        tenant_id=tenant_id,
        agent_version_id=agent_id,
        input_data=run_data.input,
        idempotency_key=validated_key,
        max_steps=run_data.limits.max_steps,
        max_cost_usd=run_data.limits.max_cost_usd,
        session_id=run_data.session_id,
        metadata=run_data.metadata,
    )

    return {
        "id": str(run.id),
        "state": run.state.value,
        "agent_version": 1,  # TODO: Get actual version from agent_version_id
        "events_url": f"/v1/runs/{run.id}/events",
    }


@router.get(
    "/{run_id}",
    response_model=RunStatusResponse,
    summary="Get run status",
    description="Get detailed status and results of a run.",
)
async def get_run_status(
    run_id: UUID,
    auth: AuthContext = Depends(require_scopes("runs:read")),
    tenant_id: UUID = Depends(get_current_tenant),
    use_cases: RunUseCases = Depends(get_run_use_cases),
) -> dict[str, Any]:
    """Get run status and results.

    Returns the current state, input/output (redacted if sensitive),
    and usage summary for the specified run.

    Requires `runs:read` scope and tenant access to the run.
    """
    status_data = await use_cases.get_run_status(run_id, tenant_id)
    if not status_data:
        from app.api.errors.exceptions import NotFoundError

        raise NotFoundError(
            message=f"Run {run_id} not found",
            resource_type="Run",
            resource_id=str(run_id),
        )

    return status_data


@router.post(
    "/{run_id}/cancel",
    summary="Cancel run",
    description="Request cancellation of a run.",
)
async def cancel_run(
    run_id: UUID,
    reason: str | None = None,
    auth: AuthContext = Depends(require_scopes("runs:write")),
    tenant_id: UUID = Depends(get_current_tenant),
    use_cases: RunUseCases = Depends(get_run_use_cases),
) -> dict[str, Any]:
    """Request cancellation of a run.

    Requests cancellation of the specified run. The cancellation is
    best-effort for in-progress operations. Workers check for cancellation
    before model calls and tool calls.

    Requires `runs:write` scope and tenant access to the run.

    Returns the current run state.
    """
    run = await use_cases.cancel_run(run_id, tenant_id, reason)
    if not run:
        from app.api.errors.exceptions import NotFoundError

        raise NotFoundError(
            message=f"Run {run_id} not found",
            resource_type="Run",
            resource_id=str(run_id),
        )

    return {
        "id": str(run.id),
        "state": run.state.value,
        "cancel_requested_at": run.cancel_requested_at.isoformat() if run.cancel_requested_at else None,
    }
