"""Agent use cases."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from app.domain.entities.agent import Agent, AgentVersion
from app.domain.entities.tool_grant import ToolGrant
from app.domain.repositories.agent import AgentRepository


class AgentUseCases:
    """Use cases for agent management."""

    def __init__(self, repository: AgentRepository) -> None:
        self._repository = repository

    async def create_agent(
        self,
        tenant_id: UUID,
        name: str,
        description: str | None = None,
    ) -> Agent:
        """Create a new agent."""
        # Check if agent with same name exists
        existing = await self._repository.get_by_name(tenant_id, name)
        if existing:
            raise ValueError(f"Agent with name '{name}' already exists")

        agent = Agent(tenant_id=tenant_id, name=name, description=description)
        return await self._repository.create(agent)

    async def get_agent(self, agent_id: UUID, tenant_id: UUID) -> Agent | None:
        """Get agent by ID with tenant check."""
        agent = await self._repository.get(agent_id)
        if agent and agent.tenant_id == tenant_id:
            return agent
        return None

    async def list_agents(
        self,
        tenant_id: UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> Sequence[Agent]:
        """List agents for tenant."""
        return await self._repository.list(tenant_id=tenant_id, limit=limit, offset=offset)

    async def update_agent(
        self,
        agent_id: UUID,
        tenant_id: UUID,
        name: str | None = None,
        description: str | None = None,
    ) -> Agent | None:
        """Update agent metadata."""
        agent = await self.get_agent(agent_id, tenant_id)
        if not agent:
            return None

        if name is not None:
            # Check name uniqueness
            existing = await self._repository.get_by_name(tenant_id, name)
            if existing and existing.id != agent_id:
                raise ValueError(f"Agent with name '{name}' already exists")
            agent.name = name

        if description is not None:
            agent.description = description

        agent.touch()
        return await self._repository.update(agent)

    async def delete_agent(self, agent_id: UUID, tenant_id: UUID) -> bool:
        """Soft delete agent."""
        agent = await self.get_agent(agent_id, tenant_id)
        if not agent:
            return False
        agent.soft_delete()
        return await self._repository.soft_delete(agent_id)

    # Version operations
    async def create_agent_version(
        self,
        agent_id: UUID,
        tenant_id: UUID,
        version: int,
        system_prompt: str,
        model_policy: dict,
        memory_mode: str,
    ) -> AgentVersion:
        """Create a new agent version."""
        agent = await self.get_agent(agent_id, tenant_id)
        if not agent:
            raise ValueError("Agent not found")

        # Check version doesn't exist
        existing = await self._repository.get_version(agent_id, version)
        if existing:
            raise ValueError(f"Version {version} already exists")

        return agent.create_version(version, system_prompt, model_policy, memory_mode)

    async def get_agent_version(
        self,
        agent_id: UUID,
        tenant_id: UUID,
        version: int,
    ) -> AgentVersion | None:
        """Get specific agent version."""
        agent = await self.get_agent(agent_id, tenant_id)
        if not agent:
            return None
        return agent.get_version(version)

    async def list_agent_versions(self, agent_id: UUID, tenant_id: UUID) -> Sequence[AgentVersion]:
        """List all versions for an agent."""
        agent = await self.get_agent(agent_id, tenant_id)
        if not agent:
            return []
        return await self._repository.list_versions(agent_id)

    async def update_agent_version(
        self,
        agent_id: UUID,
        tenant_id: UUID,
        version: int,
        system_prompt: str | None = None,
        model_policy: dict | None = None,
        memory_mode: str | None = None,
    ) -> AgentVersion | None:
        """Update a draft agent version."""
        agent = await self.get_agent(agent_id, tenant_id)
        if not agent:
            return None

        agent_version = agent.get_version(version)
        if not agent_version:
            return None

        agent_version.update(
            system_prompt=system_prompt,
            model_policy=model_policy,
            memory_mode=memory_mode,
        )
        return await self._repository.update_version(agent_version)

    async def publish_agent_version(
        self,
        agent_id: UUID,
        tenant_id: UUID,
        version: int,
    ) -> AgentVersion | None:
        """Publish an agent version."""
        agent = await self.get_agent(agent_id, tenant_id)
        if not agent:
            return None

        published = agent.publish_version(version)
        await self._repository.publish_version(agent_id, version)
        return published

    async def add_tool_grant(
        self,
        agent_id: UUID,
        tenant_id: UUID,
        version: int,
        tool_name: str,
        policy: dict,
    ) -> ToolGrant:
        """Add a tool grant to an agent version."""
        agent = await self.get_agent(agent_id, tenant_id)
        if not agent:
            raise ValueError("Agent not found")

        agent_version = agent.get_version(version)
        if not agent_version:
            raise ValueError(f"Version {version} not found")

        if not agent_version.is_mutable():
            raise ValueError("Cannot modify published or archived version")

        grant = ToolGrant(
            agent_version_id=agent_version.id,
            tool_name=tool_name,
            policy=policy,
        )
        agent_version._tool_grants.append(grant)
        return await self._repository.add_version(
            agent_version
        )  # This will update the version with grants
