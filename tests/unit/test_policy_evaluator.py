"""Tests for policy evaluator."""

from __future__ import annotations

import pytest

from app.domain.value_objects.policy import (
    PolicyCondition,
    PolicyDecision,
    PolicyEffect,
    PolicyEvaluator,
    PolicyRule,
    PolicyType,
    RateLimitInfo,
    ToolPolicy,
)


class TestPolicyEvaluator:
    """Tests for PolicyEvaluator."""

    def test_deny_all_by_default(self) -> None:
        """Test default deny policy (secure by default)."""
        policy = ToolPolicy(tool_name="test_tool")
        decision = PolicyEvaluator.evaluate(policy, "any_action")
        assert not decision.allowed
        assert not decision.requires_approval
        assert decision.reason == "Policy denies access"

    def test_explicit_allow_rule(self) -> None:
        """Test explicit allow rule."""
        policy = ToolPolicy(
            tool_name="test_tool",
            rules=[
                PolicyRule(
                    type=PolicyType.ALLOW,
                    condition=PolicyCondition(action="search"),
                    effect=PolicyEffect(allow=True),
                    priority=10,
                )
            ],
        )
        decision = PolicyEvaluator.evaluate(policy, "search")
        assert decision.allowed
        assert decision.matched_rule is not None
        assert decision.matched_rule.priority == 10

    def test_explicit_deny_rule(self) -> None:
        """Test explicit deny rule."""
        policy = ToolPolicy(
            tool_name="test_tool",
            rules=[
                PolicyRule(
                    type=PolicyType.DENY,
                    condition=PolicyCondition(action="delete"),
                    effect=PolicyEffect(allow=False),
                    priority=10,
                )
            ],
        )
        decision = PolicyEvaluator.evaluate(policy, "delete")
        assert not decision.allowed
        assert decision.reason == "Policy denies access"

    def test_require_approval_rule(self) -> None:
        """Test require approval rule."""
        policy = ToolPolicy(
            tool_name="test_tool",
            rules=[
                PolicyRule(
                    type=PolicyType.REQUIRE_APPROVAL,
                    condition=PolicyCondition(action="write"),
                    effect=PolicyEffect(allow=True, requires_approval=True),
                    priority=10,
                )
            ],
        )
        decision = PolicyEvaluator.evaluate(policy, "write")
        assert not decision.allowed
        assert decision.require_approval
        assert decision.reason == "Policy requires approval"

    def test_priority_ordering(self) -> None:
        """Test rules evaluated in priority order."""
        policy = ToolPolicy(
            tool_name="test_tool",
            rules=[
                PolicyRule(
                    type=PolicyType.DENY,
                    condition=PolicyCondition(action="write"),
                    effect=PolicyEffect(allow=False),
                    priority=5,
                ),
                PolicyRule(
                    type=PolicyType.ALLOW,
                    condition=PolicyCondition(action="write"),
                    effect=PolicyEffect(allow=True),
                    priority=10,
                ),
            ],
        )
        decision = PolicyEvaluator.evaluate(policy, "write")
        assert decision.allowed
        assert decision.matched_rule is not None
        assert decision.matched_rule.priority == 10

    def test_action_matching(self) -> None:
        """Test action condition matching."""
        policy = ToolPolicy(
            tool_name="test_tool",
            rules=[
                PolicyRule(
                    type=PolicyType.ALLOW,
                    condition=PolicyCondition(action="search"),
                    effect=PolicyEffect(allow=True),
                )
            ],
        )
        decision = PolicyEvaluator.evaluate(policy, "search")
        assert decision.allowed

        decision = PolicyEvaluator.evaluate(policy, "write")
        assert not decision.allowed  # Falls to default

    def test_resource_pattern_matching(self) -> None:
        """Test resource pattern matching with glob."""
        policy = ToolPolicy(
            tool_name="test_tool",
            rules=[
                PolicyRule(
                    type=PolicyType.ALLOW,
                    condition=PolicyCondition(resource="*.pdf"),
                    effect=PolicyEffect(allow=True),
                )
            ],
        )
        decision = PolicyEvaluator.evaluate(policy, "read", resource="document.pdf")
        assert decision.allowed

        decision = PolicyEvaluator.evaluate(policy, "read", resource="document.txt")
        assert not decision.allowed

    def test_cel_expression(self) -> None:
        """Test CEL expression evaluation."""
        policy = ToolPolicy(
            tool_name="test_tool",
            rules=[
                PolicyRule(
                    type=PolicyType.ALLOW,
                    condition=PolicyCondition(expression="context.user.role == 'admin'"),
                    effect=PolicyEffect(allow=True),
                )
            ],
        )
        decision = PolicyEvaluator.evaluate(
            policy,
            "action",
            context={"user": {"role": "admin"}},
        )
        assert decision.allowed

        decision = PolicyEvaluator.evaluate(
            policy,
            "action",
            context={"user": {"role": "user"}},
        )
        assert not decision.allowed

    def test_rate_limit_minute(self) -> None:
        """Test rate limit info for minute scope."""
        policy = ToolPolicy(
            tool_name="test_tool",
            rules=[
                PolicyRule(
                    type=PolicyType.ALLOW,
                    condition=PolicyCondition(action="search"),
                    effect=PolicyEffect(allow=True, max_calls_per_minute=60),
                )
            ],
        )
        decision = PolicyEvaluator.evaluate(policy, "search")
        assert decision.allowed
        assert decision.rate_limit is not None
        assert decision.rate_limit.limit == 60
        assert decision.rate_limit.scope == "minute"

    def test_rate_limit_hour(self) -> None:
        """Test rate limit info for hour scope."""
        policy = ToolPolicy(
            tool_name="test_tool",
            default_effect=PolicyEffect(allow=True, max_calls_per_hour=1000),
        )
        decision = PolicyEvaluator.evaluate(policy, "any")
        assert decision.rate_limit is not None
        assert decision.rate_limit.limit == 1000
        assert decision.rate_limit.scope == "hour"

    def test_rate_limit_day(self) -> None:
        """Test rate limit info for day scope."""
        policy = ToolPolicy(
            tool_name="test_tool",
            default_effect=PolicyEffect(allow=True, max_calls_per_day=10000),
        )
        decision = PolicyEvaluator.evaluate(policy, "any")
        assert decision.rate_limit is not None
        assert decision.rate_limit.limit == 10000
        assert decision.rate_limit.scope == "day"

    def test_complex_policy(self) -> None:
        """Test complex policy with multiple rules."""
        policy = ToolPolicy(
            tool_name="file_tool",
            rules=[
                PolicyRule(
                    type=PolicyType.DENY,
                    condition=PolicyCondition(resource="/etc/*"),
                    effect=PolicyEffect(allow=False),
                    priority=20,
                ),
                PolicyRule(
                    type=PolicyType.REQUIRE_APPROVAL,
                    condition=PolicyCondition(action="write", resource="*.conf"),
                    effect=PolicyEffect(allow=True, requires_approval=True),
                    priority=15,
                ),
                PolicyRule(
                    type=PolicyType.ALLOW,
                    condition=PolicyCondition(action="read"),
                    effect=PolicyEffect(allow=True),
                    priority=10,
                ),
            ],
            default_effect=PolicyEffect(allow=False),
        )

        # Deny /etc/*
        decision = PolicyEvaluator.evaluate(policy, "read", resource="/etc/passwd")
        assert not decision.allowed
        assert decision.matched_rule is not None
        assert decision.matched_rule.priority == 20

        # Require approval for write *.conf
        decision = PolicyEvaluator.evaluate(policy, "write", resource="app.conf")
        assert not decision.allowed
        assert decision.require_approval
        assert decision.matched_rule is not None
        assert decision.matched_rule.priority == 15

        # Allow read
        decision = PolicyEvaluator.evaluate(policy, "read", resource="file.txt")
        assert decision.allowed

        # Deny by default
        decision = PolicyEvaluator.evaluate(policy, "execute", resource="file.txt")
        assert not decision.allowed


class TestPolicyDecision:
    """Tests for PolicyDecision factory methods."""

    def test_allow_factory(self) -> None:
        decision = PolicyDecision.allow("test reason", metadata={"key": "value"})
        assert decision.allowed
        assert not decision.requires_approval
        assert decision.reason == "test reason"
        assert decision.metadata == {"key": "value"}

    def test_deny_factory(self) -> None:
        decision = PolicyDecision.deny("denied", metadata={"key": "value"})
        assert not decision.allowed
        assert not decision.requires_approval
        assert decision.reason == "denied"

    def test_require_approval_factory(self) -> None:
        decision = PolicyDecision.require_approval("needs approval")
        assert not decision.allowed
        assert decision.requires_approval
        assert decision.reason == "needs approval"