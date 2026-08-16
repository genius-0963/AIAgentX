"""Agent repository protocol."""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from app.domain.entities.agent import Agent, AgentVersion


class AgentRepository(Protocol):
    """Repository for agent operations."""

    async def create(self, agent: Agent) -> Agent:
        """Create a new agent."""
        ...

    async def get(self, agent_id: UUID) -> Agent | None:
        """Get agent by ID with all versions."""
        ...

    async def get_by_name(self, tenant_id: UUID, name: str) -> Agent | None:
        """Get agent by name within tenant."""
        ...

    async def update(self, agent: Agent) -> Agent:
        """Update agent."""
        ...

    async def list(
        self,
        tenant_id: UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Agent]:
        """List agents for tenant."""
        ...

    async def soft_delete(self, agent_id: UUID) -> bool:
        """Soft delete agent."""
        ...

    # Version operations
    async def add_version(self, version: AgentVersion) -> AgentVersion:
        """Add a version to an agent."""
        ...

    async def get_version(self, agent_id: UUID, version: int) -> AgentVersion | None:
        """Get specific agent version."""
        ...

    async def get_published_version(self, agent_id: UUID) -> AgentVersion | None:
        """Get published version of agent."""
        ...

    async def update_version(self, version: AgentVersion) -> AgentVersion:
        """Update agent version."""
        ...

    async def publish_version(self, agent_id: UUID, version: int) -> AgentVersion:
        """Publish a version (archives current published)."""
        ...

    async def list_versions(self, agent_id: UUID) -> list[AgentVersion]:
        """List all versions for an agent."""
        ...
