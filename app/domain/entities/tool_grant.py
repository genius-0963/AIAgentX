"""ToolGrant entity."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from app.domain.entities.base import Entity
from app.domain.value_objects.policy import (
    PolicyDecision,
    PolicyEvaluator,
    PolicyRule,
    PolicyType,
    PolicyCondition,
    PolicyEffect,
    ToolPolicy,
)


@dataclass(slots=True, kw_only=True)
class ToolGrant(Entity):
    """Tool grant entity with enhanced policy support."""

    agent_version_id: UUID
    tool_name: str
    policy: ToolPolicy
    is_active: bool = True

    def __post_init__(self) -> None:
        if not self.tool_name or not self.tool_name.strip():
            raise ValueError("Tool name cannot be empty")
        if not isinstance(self.policy, ToolPolicy):
            raise ValueError("Policy must be a ToolPolicy instance")

    def update_policy(self, policy: ToolPolicy) -> None:
        """Update the tool policy."""
        if not isinstance(policy, ToolPolicy):
            raise ValueError("Policy must be a ToolPolicy instance")
        self.policy = policy
        self.touch()

    def evaluate(
        self,
        action: str,
        resource: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> PolicyDecision:
        """Evaluate policy for a tool action."""
        if not self.is_active:
            return PolicyDecision.deny("Grant is inactive")
        return PolicyEvaluator.evaluate(self.policy, action, resource, context)

    def allows(
        self,
        action: str,
        resource: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> bool:
        """Check if the grant allows a specific action (backward compatible)."""
        return self.evaluate(action, resource, context).allowed

    @classmethod
    def from_legacy_dict(
        cls,
        agent_version_id: UUID,
        tool_name: str,
        policy_dict: dict[str, Any],
        is_active: bool = True,
    ) -> ToolGrant:
        """Create ToolGrant from legacy policy dict."""
        allowed_actions = policy_dict.get("allowed_actions", [])
        allowed_resources = policy_dict.get("allowed_resources", [])

        rules = []
        if allowed_actions:
            # Create rules for each allowed action
            for action in allowed_actions:
                rules.append(
                    PolicyRule(
                        type=PolicyType.ALLOW,
                        condition=PolicyCondition(action=action),
                        effect=PolicyEffect(allow=True),
                        priority=10,
                    )
                )

        # Default behavior: if no allowed_actions specified, use allow_by_default
        # If allowed_actions specified but allow_by_default is False, deny by default
        default_allow = policy_dict.get("allow_by_default", not bool(allowed_actions))

        tool_policy = ToolPolicy(
            tool_name=tool_name,
            rules=rules,
            default_effect=PolicyEffect(allow=default_allow),
            metadata=policy_dict.get("metadata", {}),
        )

        return cls(
            agent_version_id=agent_version_id,
            tool_name=tool_name,
            policy=tool_policy,
            is_active=is_active,
        )