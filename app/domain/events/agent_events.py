"""Agent domain events."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID


@dataclass(frozen=True, slots=True)
class AgentCreated:
    """Event fired when an agent is created."""

    tenant_id: UUID
    name: str
    description: str | None = None


@dataclass(frozen=True, slots=True)
class AgentVersionCreated:
    """Event fired when an agent version is created."""

    tenant_id: UUID
    agent_id: UUID
    version: int
    system_prompt: str
    model_policy: dict[str, Any]
    memory_mode: str


@dataclass(frozen=True, slots=True)
class AgentPublished:
    """Event fired when an agent version is published."""

    tenant_id: UUID
    agent_id: UUID
    version: int


@dataclass(frozen=True, slots=True)
class AgentDeleted:
    """Event fired when an agent is deleted (soft)."""

    tenant_id: UUID
    agent_id: UUID
