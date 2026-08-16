"""Agent and AgentVersion entities."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any
from uuid import UUID

from app.domain.entities.base import AggregateRoot, Entity
from app.domain.entities.tool_grant import ToolGrant


class AgentStatus(StrEnum):
    """Agent version status."""

    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


@dataclass(slots=True, kw_only=True)
class Agent(AggregateRoot):
    """Agent aggregate root."""

    tenant_id: UUID
    name: str
    description: str | None = None
    _versions: list[AgentVersion] = field(default_factory=list, init=False, repr=False)

    def __post_init__(self) -> None:
        if not self.name or not self.name.strip():
            raise ValueError("Agent name cannot be empty")
        if len(self.name) > 200:
            raise ValueError("Agent name too long (max 200 characters)")

    def create_version(
        self,
        version: int,
        system_prompt: str,
        model_policy: dict[str, Any],
        memory_mode: str,
    ) -> AgentVersion:
        """Create a new agent version."""
        if version <= 0:
            raise ValueError("Version must be positive")
        if any(v.version == version for v in self._versions):
            raise ValueError(f"Version {version} already exists")
        if not system_prompt or not system_prompt.strip():
            raise ValueError("System prompt cannot be empty")

        agent_version = AgentVersion(
            agent_id=self.id,
            tenant_id=self.tenant_id,
            version=version,
            system_prompt=system_prompt,
            model_policy=model_policy,
            memory_mode=memory_mode,
            status=AgentStatus.DRAFT,
        )
        self._versions.append(agent_version)
        self.touch()
        self.add_event(
            {
                "type": "AgentVersionCreated",
                "tenant_id": self.tenant_id,
                "agent_id": self.id,
                "version": version,
                "system_prompt": system_prompt,
                "model_policy": model_policy,
                "memory_mode": memory_mode,
            }
        )
        return agent_version

    def get_version(self, version: int) -> AgentVersion | None:
        """Get a specific version."""
        return next((v for v in self._versions if v.version == version), None)

    def get_latest_version(self) -> AgentVersion | None:
        """Get the latest version."""
        if not self._versions:
            return None
        return max(self._versions, key=lambda v: v.version)

    def get_published_version(self) -> AgentVersion | None:
        """Get the published version."""
        return next((v for v in self._versions if v.status == AgentStatus.PUBLISHED), None)

    def publish_version(self, version: int) -> AgentVersion:
        """Publish a specific version (makes it immutable)."""
        agent_version = self.get_version(version)
        if agent_version is None:
            raise ValueError(f"Version {version} not found")
        if agent_version.status == AgentStatus.PUBLISHED:
            return agent_version  # Idempotent

        # Archive any currently published version
        for v in self._versions:
            if v.status == AgentStatus.PUBLISHED:
                v.status = AgentStatus.ARCHIVED
                v.touch()

        agent_version.status = AgentStatus.PUBLISHED
        agent_version.touch()
        self.touch()
        self.add_event(
            {
                "type": "AgentPublished",
                "tenant_id": self.tenant_id,
                "agent_id": self.id,
                "version": version,
            }
        )
        return agent_version

    def soft_delete(self) -> None:
        """Soft delete the agent."""
        self.touch()
        self.add_event({"type": "AgentDeleted", "tenant_id": self.tenant_id, "agent_id": self.id})


@dataclass(slots=True, kw_only=True)
class AgentVersion(Entity):
    """Agent version entity (part of Agent aggregate)."""

    agent_id: UUID
    tenant_id: UUID
    version: int
    system_prompt: str
    model_policy: dict[str, Any]
    memory_mode: str
    status: AgentStatus = AgentStatus.DRAFT
    _tool_grants: list[ToolGrant] = field(default_factory=list, init=False, repr=False)

    def __post_init__(self) -> None:
        if self.version <= 0:
            raise ValueError("Version must be positive")
        if not self.system_prompt or not self.system_prompt.strip():
            raise ValueError("System prompt cannot be empty")
        if not isinstance(self.model_policy, dict):
            raise ValueError("Model policy must be a dictionary")
        if not self.memory_mode:
            raise ValueError("Memory mode cannot be empty")

    def is_published(self) -> bool:
        """Check if this version is published."""
        return self.status == AgentStatus.PUBLISHED

    def is_mutable(self) -> bool:
        """Check if this version can be modified."""
        return self.status == AgentStatus.DRAFT

    def update(
        self,
        system_prompt: str | None = None,
        model_policy: dict[str, Any] | None = None,
        memory_mode: str | None = None,
    ) -> None:
        """Update the draft version."""
        if not self.is_mutable():
            raise ValueError("Cannot modify published or archived version")

        if system_prompt is not None:
            if not system_prompt.strip():
                raise ValueError("System prompt cannot be empty")
            self.system_prompt = system_prompt
        if model_policy is not None:
            if not isinstance(model_policy, dict):
                raise ValueError("Model policy must be a dictionary")
            self.model_policy = model_policy
        if memory_mode is not None:
            if not memory_mode:
                raise ValueError("Memory mode cannot be empty")
            self.memory_mode = memory_mode
        self.touch()
