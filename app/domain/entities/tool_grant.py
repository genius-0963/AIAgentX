"""ToolGrant entity."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from app.domain.entities.base import Entity


@dataclass(slots=True, kw_only=True)
class ToolGrant(Entity):
    """Tool grant entity (part of AgentVersion aggregate)."""

    agent_version_id: UUID
    tool_name: str
    policy: dict[str, Any]

    def __post_init__(self) -> None:
        if not self.tool_name or not self.tool_name.strip():
            raise ValueError("Tool name cannot be empty")
        if not isinstance(self.policy, dict):
            raise ValueError("Policy must be a dictionary")

    def update_policy(self, policy: dict[str, Any]) -> None:
        """Update the tool policy."""
        if not isinstance(policy, dict):
            raise ValueError("Policy must be a dictionary")
        self.policy = policy
        self.touch()

    def allows(self, action: str, resource: str | None = None) -> bool:
        """Check if the grant allows a specific action."""
        # Simple policy check - can be extended
        allowed_actions = self.policy.get("allowed_actions", [])
        if allowed_actions and action not in allowed_actions:
            return False

        if resource:
            allowed_resources = self.policy.get("allowed_resources", [])
            if allowed_resources and resource not in allowed_resources:
                return False

        return True
