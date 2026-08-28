"""Agent CRUD API endpoints."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.schemas.agents import (
    AgentCreate,
    AgentResponse,
    AgentUpdate,
    AgentVersionCreate,
    AgentVersionResponse,
    AgentVersionUpdate,
    ToolGrantCreate,
    ToolGrantResponse,
)
from app.application.use_cases.agent import AgentUseCases
from app.domain.entities.agent import Agent, AgentVersion
from app.domain.entities.tool_grant import ToolGrant
from app.infrastructure.auth.middleware import (
    AuthContext,
    get_auth_context,
    get_current_tenant,
    require_scopes,
)
from app.infrastructure.db.repositories.agent import SQLAgentRepository
from app.infrastructure.db.session import get_db_session as get_session

router = APIRouter(prefix="/agents", tags=["agents"])


async def get_agent_use_cases(
    session: AsyncSession = Depends(get_session),
) -> AgentUseCases:
    """Dependency to get agent use cases."""
    repository = SQLAgentRepository(session)
    return AgentUseCases(repository)


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=AgentResponse,
    summary="Create agent",
    description="Create a new agent definition with version 1 as draft.",
)
async def create_agent(
    agent_data: AgentCreate,
    auth: AuthContext = Depends(require_scopes("agents:write")),
    tenant_id: UUID = Depends(get_current_tenant),
    use_cases: AgentUseCases = Depends(get_agent_use_cases),
) -> AgentResponse:
    """Create a new agent definition.

    Creates a new agent with the given name and optional description.
    The first version (version 1) is created as a draft and must be
    configured separately before publishing.

    Requires `agents:write` scope.
    """
    agent = await use_cases.create_agent(
        tenant_id=tenant_id,
        name=agent_data.name,
        description=agent_data.description,
    )
    return AgentResponse(
        id=agent.id,
        tenant_id=agent.tenant_id,
        name=agent.name,
        description=agent.description,
        versions=[],
        created_at=agent.created_at.isoformat(),
        updated_at=agent.updated_at.isoformat(),
    )


@router.get(
    "",
    response_model=list[AgentResponse],
    summary="List agents",
    description="List all agents for the current tenant with pagination.",
)
async def list_agents(
    limit: int = 50,
    offset: int = 0,
    auth: AuthContext = Depends(require_scopes("agents:read")),
    tenant_id: UUID = Depends(get_current_tenant),
    use_cases: AgentUseCases = Depends(get_agent_use_cases),
) -> list[Agent]:
    """List agents for the current tenant.

    Returns a paginated list of agents belonging to the current tenant.
    Requires `agents:read` scope.
    """
    if limit > 100:
        limit = 100  # Enforce maximum limit
    return await use_cases.list_agents(
        tenant_id=tenant_id,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{agent_id}",
    response_model=AgentResponse,
    summary="Get agent",
    description="Get detailed information about a specific agent.",
)
async def get_agent(
    agent_id: UUID,
    auth: AuthContext = Depends(require_scopes("agents:read")),
    tenant_id: UUID = Depends(get_current_tenant),
    use_cases: AgentUseCases = Depends(get_agent_use_cases),
) -> Agent:
    """Get agent by ID.

    Returns detailed information about the specified agent including
    all versions. Requires `agents:read` scope and tenant access.
    """
    agent = await use_cases.get_agent(agent_id, tenant_id)
    if not agent:
        from app.api.errors.exceptions import NotFoundError

        raise NotFoundError(
            message=f"Agent {agent_id} not found",
            resource_type="Agent",
            resource_id=str(agent_id),
        )
    return agent


@router.patch(
    "/{agent_id}",
    response_model=AgentResponse,
    summary="Update agent",
    description="Update agent metadata (name and description).",
)
async def update_agent(
    agent_id: UUID,
    agent_data: AgentUpdate,
    auth: AuthContext = Depends(require_scopes("agents:write")),
    tenant_id: UUID = Depends(get_current_tenant),
    use_cases: AgentUseCases = Depends(get_agent_use_cases),
) -> Agent:
    """Update agent metadata.

    Updates the name and/or description of an existing agent.
    Requires `agents:write` scope and tenant access.
    """
    agent = await use_cases.update_agent(
        agent_id=agent_id,
        tenant_id=tenant_id,
        name=agent_data.name,
        description=agent_data.description,
    )
    if not agent:
        from app.api.errors.exceptions import NotFoundError

        raise NotFoundError(
            message=f"Agent {agent_id} not found",
            resource_type="Agent",
            resource_id=str(agent_id),
        )
    return agent


@router.delete(
    "/{agent_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete agent",
    description="Soft delete an agent definition.",
)
async def delete_agent(
    agent_id: UUID,
    auth: AuthContext = Depends(require_scopes("agents:write")),
    tenant_id: UUID = Depends(get_current_tenant),
    use_cases: AgentUseCases = Depends(get_agent_use_cases),
) -> None:
    """Soft delete an agent.

    Marks the agent as deleted. The agent and its data are retained
    in the database but not returned in API responses.
    Requires `agents:write` scope and tenant access.
    """
    deleted = await use_cases.delete_agent(agent_id, tenant_id)
    if not deleted:
        from app.api.errors.exceptions import NotFoundError

        raise NotFoundError(
            message=f"Agent {agent_id} not found",
            resource_type="Agent",
            resource_id=str(agent_id),
        )


# Version management endpoints
@router.post(
    "/{agent_id}/versions",
    status_code=status.HTTP_201_CREATED,
    response_model=AgentVersionResponse,
    summary="Create agent version",
    description="Create a new version of an agent.",
)
async def create_agent_version(
    agent_id: UUID,
    version_data: AgentVersionCreate,
    auth: AuthContext = Depends(require_scopes("agents:write")),
    tenant_id: UUID = Depends(get_current_tenant),
    use_cases: AgentUseCases = Depends(get_agent_use_cases),
) -> AgentVersion:
    """Create a new agent version.

    Creates a new version of the specified agent with the given
    configuration. The version starts in draft status and must be
    published before it can be used for runs.

    Requires `agents:write` scope and tenant access to the agent.
    """
    version = await use_cases.create_agent_version(
        agent_id=agent_id,
        tenant_id=tenant_id,
        version=version_data.version,
        system_prompt=version_data.system_prompt,
        model_policy=version_data.model_policy,
        memory_mode=version_data.memory_mode,
    )
    return version


@router.get(
    "/{agent_id}/versions",
    response_model=list[AgentVersionResponse],
    summary="List agent versions",
    description="List all versions of an agent.",
)
async def list_agent_versions(
    agent_id: UUID,
    auth: AuthContext = Depends(require_scopes("agents:read")),
    tenant_id: UUID = Depends(get_current_tenant),
    use_cases: AgentUseCases = Depends(get_agent_use_cases),
) -> list[AgentVersion]:
    """List all versions of an agent.

    Returns all versions of the specified agent, including draft,
    published, and archived versions.

    Requires `agents:read` scope and tenant access to the agent.
    """
    return await use_cases.list_agent_versions(agent_id, tenant_id)


@router.get(
    "/{agent_id}/versions/{version}",
    response_model=AgentVersionResponse,
    summary="Get agent version",
    description="Get detailed information about a specific agent version.",
)
async def get_agent_version(
    agent_id: UUID,
    version: int,
    auth: AuthContext = Depends(require_scopes("agents:read")),
    tenant_id: UUID = Depends(get_current_tenant),
    use_cases: AgentUseCases = Depends(get_agent_use_cases),
) -> AgentVersion:
    """Get a specific agent version.

    Returns detailed information about the specified agent version,
    including tool grants and configuration.

    Requires `agents:read` scope and tenant access to the agent.
    """
    agent_version = await use_cases.get_agent_version(agent_id, tenant_id, version)
    if not agent_version:
        from app.api.errors.exceptions import NotFoundError

        raise NotFoundError(
            message=f"Agent version {version} not found for agent {agent_id}",
            resource_type="AgentVersion",
            resource_id=f"{agent_id}/v{version}",
        )
    return agent_version


@router.patch(
    "/{agent_id}/versions/{version}",
    response_model=AgentVersionResponse,
    summary="Update agent version",
    description="Update a draft agent version.",
)
async def update_agent_version(
    agent_id: UUID,
    version: int,
    version_data: AgentVersionUpdate,
    auth: AuthContext = Depends(require_scopes("agents:write")),
    tenant_id: UUID = Depends(get_current_tenant),
    use_cases: AgentUseCases = Depends(get_agent_use_cases),
) -> AgentVersion:
    """Update a draft agent version.

    Updates the configuration of a draft agent version. Published and
    archived versions cannot be modified.

    Requires `agents:write` scope and tenant access to the agent.
    """
    agent_version = await use_cases.update_agent_version(
        agent_id=agent_id,
        tenant_id=tenant_id,
        version=version,
        system_prompt=version_data.system_prompt,
        model_policy=version_data.model_policy,
        memory_mode=version_data.memory_mode,
    )
    if not agent_version:
        from app.api.errors.exceptions import NotFoundError

        raise NotFoundError(
            message=f"Agent version {version} not found for agent {agent_id}",
            resource_type="AgentVersion",
            resource_id=f"{agent_id}/v{version}",
        )
    return agent_version


@router.post(
    "/{agent_id}/versions/{version}/publish",
    response_model=AgentVersionResponse,
    summary="Publish agent version",
    description="Publish a draft agent version.",
)
async def publish_agent_version(
    agent_id: UUID,
    version: int,
    auth: AuthContext = Depends(require_scopes("agents:write")),
    tenant_id: UUID = Depends(get_current_tenant),
    use_cases: AgentUseCases = Depends(get_agent_use_cases),
) -> AgentVersion:
    """Publish an agent version.

    Publishes a draft agent version, making it immutable and available
    for use in runs. Any currently published version will be archived.

    Requires `agents:write` scope and tenant access to the agent.
    """
    agent_version = await use_cases.publish_agent_version(agent_id, tenant_id, version)
    if not agent_version:
        from app.api.errors.exceptions import NotFoundError

        raise NotFoundError(
            message=f"Agent version {version} not found for agent {agent_id}",
            resource_type="AgentVersion",
            resource_id=f"{agent_id}/v{version}",
        )
    return agent_version


@router.post(
    "/{agent_id}/versions/{version}/tool-grants",
    status_code=status.HTTP_201_CREATED,
    response_model=ToolGrantResponse,
    summary="Add tool grant",
    description="Add a tool grant to an agent version.",
)
async def create_tool_grant(
    agent_id: UUID,
    version: int,
    grant_data: ToolGrantCreate,
    auth: AuthContext = Depends(require_scopes("agents:write")),
    tenant_id: UUID = Depends(get_current_tenant),
    use_cases: AgentUseCases = Depends(get_agent_use_cases),
) -> ToolGrant:
    """Add a tool grant to an agent version.

    Grants access to a specific tool for the agent version with the
    specified access policy. Only draft versions can be modified.

    Requires `agents:write` scope and tenant access to the agent.
    """
    tool_grant = await use_cases.add_tool_grant(
        agent_id=agent_id,
        tenant_id=tenant_id,
        version=version,
        tool_name=grant_data.tool_name,
        policy=grant_data.policy,
    )
    return tool_grant