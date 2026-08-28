"""Tests for ToolGrant entity."""

from __future__ import annotations

import pytest
from uuid import UUID, uuid4

from app.domain.entities.tool_grant import ToolGrant
from app.domain.value_objects.policy import (
    PolicyCondition,
    PolicyDecision,
    PolicyEffect,
    PolicyRule,
    PolicyType,
    ToolPolicy,
)


class TestToolGrant:
    """Tests for ToolGrant entity."""

    def test_create_tool_grant(self) -> None:
        """Test creating a tool grant."""
        agent_version_id = uuid4()
        policy = ToolPolicy(tool_name="web_search")

        grant = ToolGrant(
            agent_version_id=agent_version_id,
            tool_name="web_search",
            policy=policy,
        )

        assert grant.agent_version_id == agent_version_id
        assert grant.tool_name == "web_search"
        assert grant.policy == policy
        assert grant.is_active is True

    def test_create_inactive_grant(self) -> None:
        """Test creating inactive grant."""
        agent_version_id = uuid4()
        policy = ToolPolicy(tool_name="web_search")

        grant = ToolGrant(
            agent_version_id=agent_version_id,
            tool_name="web_search",
            policy=policy,
            is_active=False,
        )

        assert grant.is_active is False

    def test_validation_empty_tool_name(self) -> None:
        """Test validation rejects empty tool name."""
        agent_version_id = uuid4()
        policy = ToolPolicy(tool_name="test")

        with pytest.raises(ValueError, match="Tool name cannot be empty"):
            ToolGrant(
                agent_version_id=agent_version_id,
                tool_name="",
                policy=policy,
            )

    def test_validation_invalid_policy(self) -> None:
        """Test validation rejects non-ToolPolicy."""
        agent_version_id = uuid4()

        with pytest.raises(ValueError, match="Policy must be a ToolPolicy instance"):
            ToolGrant(
                agent_version_id=agent_version_id,
                tool_name="test",
                policy={},  # type: ignore
            )

    def test_evaluate_allows(self) -> None:
        """Test evaluate returns allow decision."""
        agent_version_id = uuid4()
        policy = ToolPolicy(
            tool_name="web_search",
            rules=[
                PolicyRule(
                    type=PolicyType.ALLOW,
                    condition=PolicyCondition(action="search"),
                    effect=PolicyEffect(allow=True),
                )
            ],
        )
        grant = ToolGrant(
            agent_version_id=agent_version_id,
            tool_name="web_search",
            policy=policy,
        )

        decision = grant.evaluate("search")
        assert decision.allowed
        assert not decision.requires_approval

    def test_evaluate_requires_approval(self) -> None:
        """Test evaluate returns require approval."""
        agent_version_id = uuid4()
        policy = ToolPolicy(
            tool_name="file_write",
            rules=[
                PolicyRule(
                    type=PolicyType.REQUIRE_APPROVAL,
                    condition=PolicyCondition(action="write"),
                    effect=PolicyEffect(allow=True, requires_approval=True),
                )
            ],
        )
        grant = ToolGrant(
            agent_version_id=agent_version_id,
            tool_name="file_write",
            policy=policy,
        )

        decision = grant.evaluate("write")
        assert not decision.allowed
        assert decision.require_approval

    def test_evaluate_denies(self) -> None:
        """Test evaluate returns deny."""
        agent_version_id = uuid4()
        policy = ToolPolicy(
            tool_name="dangerous_tool",
            rules=[
                PolicyRule(
                    type=PolicyType.DENY,
                    condition=PolicyCondition(action="delete"),
                    effect=PolicyEffect(allow=False),
                )
            ],
        )
        grant = ToolGrant(
            agent_version_id=agent_version_id,
            tool_name="dangerous_tool",
            policy=policy,
        )

        decision = grant.evaluate("delete")
        assert not decision.allowed
        assert not decision.requires_approval
        assert decision.reason == "Policy denies access"
        assert decision.reason == "Policy denies access"

    def test_inactive_grant_denies(self) -> None:
        """Test inactive grant denies all."""
        agent_version_id = uuid4()
        policy = ToolPolicy(tool_name="test")
        grant = ToolGrant(
            agent_version_id=agent_version_id,
            tool_name="test",
            policy=policy,
            is_active=False,
        )

        decision = grant.evaluate("any")
        assert not decision.allowed
        assert decision.reason == "Grant is inactive"

    def test_allows_backward_compatible(self) -> None:
        """Test allows method for backward compatibility."""
        agent_version_id = uuid4()
        policy = ToolPolicy(
            tool_name="test",
            rules=[
                PolicyRule(
                    type=PolicyType.ALLOW,
                    condition=PolicyCondition(action="allowed"),
                    effect=PolicyEffect(allow=True),
                )
            ],
        )
        grant = ToolGrant(
            agent_version_id=agent_version_id,
            tool_name="test",
            policy=policy,
        )

        assert grant.allows("allowed")
        assert not grant.allows("denied")

    def test_update_policy(self) -> None:
        """Test updating policy."""
        agent_version_id = uuid4()
        policy1 = ToolPolicy(tool_name="test")
        policy2 = ToolPolicy(tool_name="test", version=2)

        grant = ToolGrant(
            agent_version_id=agent_version_id,
            tool_name="test",
            policy=policy1,
        )

        grant.update_policy(policy2)
        assert grant.policy == policy2
        assert grant.policy.version == 2

    def test_update_policy_invalid(self) -> None:
        """Test updating with invalid policy."""
        agent_version_id = uuid4()
        policy = ToolPolicy(tool_name="test")
        grant = ToolGrant(
            agent_version_id=agent_version_id,
            tool_name="test",
            policy=policy,
        )

        with pytest.raises(ValueError, match="Policy must be a ToolPolicy instance"):
            grant.update_policy({})  # type: ignore

    def test_from_legacy_dict(self) -> None:
        """Test creating from legacy policy dict."""
        agent_version_id = uuid4()
        legacy_policy = {
            "allowed_actions": ["search", "read"],
            "allowed_resources": ["*.pdf"],
            "allow_by_default": False,
            "metadata": {"version": "1.0"},
        }

        grant = ToolGrant.from_legacy_dict(
            agent_version_id=agent_version_id,
            tool_name="web_search",
            policy_dict=legacy_policy,
        )

        assert grant.tool_name == "web_search"
        assert grant.policy.tool_name == "web_search"
        assert grant.policy.metadata == {"version": "1.0"}
        assert grant.policy.default_effect.allow is False

        # Test it evaluates correctly
        decision = grant.evaluate("search")
        assert decision.allowed

        decision = grant.evaluate("write")
        assert not decision.allowed

    def test_from_legacy_dict_allow_by_default(self) -> None:
        """Test legacy dict with allow_by_default true."""
        agent_version_id = uuid4()
        legacy_policy = {
            "allowed_actions": ["search"],
            "allow_by_default": True,
        }

        grant = ToolGrant.from_legacy_dict(
            agent_version_id=agent_version_id,
            tool_name="test",
            policy_dict=legacy_policy,
        )

        # Action in allowed list
        decision = grant.evaluate("search")
        assert decision.allowed

        # Action not in list but default allows
        decision = grant.evaluate("other")
        assert decision.allowed