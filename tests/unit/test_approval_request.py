"""Tests for approval request entity."""

from __future__ import annotations

import pytest
from datetime import datetime, UTC, timedelta
from uuid import UUID, uuid4

from app.domain.entities.approval_request import (
    ApprovalRequest,
    ApprovalState,
    ApprovalType,
)


class TestApprovalRequest:
    """Tests for ApprovalRequest entity."""

    def test_create_approval_request(self) -> None:
        """Test creating an approval request."""
        run_id = uuid4()
        request = ApprovalRequest(
            run_id=run_id,
            step_sequence=1,
            approval_type=ApprovalType.TOOL_EXECUTION,
            tool_name="web_search",
            action="search",
            input_data={"query": "test"},
            policy_reason="Rate limit exceeded",
            requested_by="executor",
        )

        assert request.run_id == run_id
        assert request.step_sequence == 1
        assert request.approval_type == ApprovalType.TOOL_EXECUTION
        assert request.state == ApprovalState.PENDING
        assert request.tool_name == "web_search"
        assert request.action == "search"
        assert request.policy_reason == "Rate limit exceeded"
        assert request.requested_by == "executor"
        assert request.expires_at is not None
        assert request.ttl_seconds == 3600

    def test_create_with_custom_ttl(self) -> None:
        """Test creating with custom TTL."""
        run_id = uuid4()
        request = ApprovalRequest(
            run_id=run_id,
            step_sequence=1,
            approval_type=ApprovalType.TOOL_EXECUTION,
            tool_name="test",
            action="test",
            ttl_seconds=7200,
        )
        assert request.ttl_seconds == 7200
        # expires_at should be ~2 hours from now
        expected = datetime.now(UTC) + timedelta(seconds=7200)
        assert abs((request.expires_at - expected).total_seconds()) < 5

    def test_approve_request(self) -> None:
        """Test approving a request."""
        run_id = uuid4()
        request = ApprovalRequest(
            run_id=run_id,
            step_sequence=1,
            approval_type=ApprovalType.TOOL_EXECUTION,
            tool_name="test",
            action="test",
        )

        request.approve("user123", {"result": "approved"})

        assert request.state == ApprovalState.APPROVED
        assert request.approved_by == "user123"
        assert request.approved_at is not None
        assert request.response_data == {"result": "approved"}
        # Check event was added
        events = request.collect_events()
        assert len(events) == 1
        assert events[0].__class__.__name__ == "ApprovalGranted"

    def test_deny_request(self) -> None:
        """Test denying a request."""
        run_id = uuid4()
        request = ApprovalRequest(
            run_id=run_id,
            step_sequence=1,
            approval_type=ApprovalType.TOOL_EXECUTION,
            tool_name="test",
            action="test",
        )

        request.deny("user123", "Not allowed")

        assert request.state == ApprovalState.DENIED
        assert request.approved_by == "user123"
        assert request.approved_at is not None
        assert request.denial_reason == "Not allowed"
        events = request.collect_events()
        assert len(events) == 1
        assert events[0].__class__.__name__ == "ApprovalDenied"

    def test_cannot_approve_non_pending(self) -> None:
        """Test cannot approve non-pending request."""
        run_id = uuid4()
        request = ApprovalRequest(
            run_id=run_id,
            step_sequence=1,
            approval_type=ApprovalType.TOOL_EXECUTION,
            tool_name="test",
            action="test",
        )
        request.approve("user1")

        with pytest.raises(ValueError, match="Cannot approve request in state"):
            request.approve("user2")

    def test_cannot_deny_non_pending(self) -> None:
        """Test cannot deny non-pending request."""
        run_id = uuid4()
        request = ApprovalRequest(
            run_id=run_id,
            step_sequence=1,
            approval_type=ApprovalType.TOOL_EXECUTION,
            tool_name="test",
            action="test",
        )
        request.deny("user1", "reason")

        with pytest.raises(ValueError, match="Cannot deny request in state"):
            request.deny("user2", "reason")

    def test_expired_request_cannot_approve(self) -> None:
        """Test expired request cannot be approved."""
        run_id = uuid4()
        request = ApprovalRequest(
            run_id=run_id,
            step_sequence=1,
            approval_type=ApprovalType.TOOL_EXECUTION,
            tool_name="test",
            action="test",
            ttl_seconds=0,
            expires_at=datetime.now(UTC) - timedelta(seconds=1),
        )

        with pytest.raises(ValueError, match="expired"):
            request.approve("user1")

    def test_cancel_request(self) -> None:
        """Test cancelling a request."""
        run_id = uuid4()
        request = ApprovalRequest(
            run_id=run_id,
            step_sequence=1,
            approval_type=ApprovalType.TOOL_EXECUTION,
            tool_name="test",
            action="test",
        )

        request.cancel("User cancelled")

        assert request.state == ApprovalState.CANCELLED
        assert request.denial_reason == "User cancelled"
        events = request.collect_events()
        assert len(events) == 1
        assert events[0].__class__.__name__ == "ApprovalCancelled"

    def test_cancel_approved_request(self) -> None:
        """Test cancelling an approved request."""
        run_id = uuid4()
        request = ApprovalRequest(
            run_id=run_id,
            step_sequence=1,
            approval_type=ApprovalType.TOOL_EXECUTION,
            tool_name="test",
            action="test",
        )
        request.approve("user1")
        request.cancel("Cancelled after approval")

        assert request.state == ApprovalState.CANCELLED

    def test_is_expired(self) -> None:
        """Test is_expired method."""
        run_id = uuid4()
        request = ApprovalRequest(
            run_id=run_id,
            step_sequence=1,
            approval_type=ApprovalType.TOOL_EXECUTION,
            tool_name="test",
            action="test",
        )
        assert not request.is_expired()

        request.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        assert request.is_expired()

    def test_validation_empty_tool_name(self) -> None:
        """Test validation rejects empty tool name."""
        run_id = uuid4()
        with pytest.raises(ValueError, match="Tool name cannot be empty"):
            ApprovalRequest(
                run_id=run_id,
                step_sequence=1,
                approval_type=ApprovalType.TOOL_EXECUTION,
                tool_name="",
                action="test",
            )

    def test_validation_empty_action(self) -> None:
        """Test validation rejects empty action."""
        run_id = uuid4()
        with pytest.raises(ValueError, match="Action cannot be empty"):
            ApprovalRequest(
                run_id=run_id,
                step_sequence=1,
                approval_type=ApprovalType.TOOL_EXECUTION,
                tool_name="test",
                action="",
            )

    def test_approval_types(self) -> None:
        """Test all approval types."""
        for approval_type in ApprovalType:
            run_id = uuid4()
            request = ApprovalRequest(
                run_id=run_id,
                step_sequence=1,
                approval_type=approval_type,
                tool_name="test",
                action="test",
            )
            assert request.approval_type == approval_type

    def test_approval_states(self) -> None:
        """Test all approval states."""
        for state in ApprovalState:
            assert state in ApprovalState