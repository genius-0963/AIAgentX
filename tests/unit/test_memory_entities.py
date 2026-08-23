"""Unit tests for memory domain entities."""

from __future__ import annotations

import pytest
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from app.domain.entities.memory import (
    AllowedUseLabel,
    MemoryRecord,
    MemoryRetentionPolicy,
    MemoryScope,
    SessionSummary,
    MemoryAggregate,
)


class TestMemoryScope:
    """Tests for MemoryScope enum."""

    def test_scopes_exist(self) -> None:
        assert MemoryScope.EPHEMERAL == "ephemeral"
        assert MemoryScope.SESSION == "session"
        assert MemoryScope.DURABLE == "durable"

    def test_scope_values(self) -> None:
        assert set(MemoryScope) == {"ephemeral", "session", "durable"}


class TestAllowedUseLabel:
    """Tests for AllowedUseLabel enum."""

    def test_labels_exist(self) -> None:
        assert AllowedUseLabel.PUBLIC == "public"
        assert AllowedUseLabel.INTERNAL == "internal"
        assert AllowedUseLabel.CONFIDENTIAL == "confidential"
        assert AllowedUseLabel.RESTRICTED == "restricted"

    def test_label_values(self) -> None:
        assert set(AllowedUseLabel) == {"public", "internal", "confidential", "restricted"}


class TestMemoryRecord:
    """Tests for MemoryRecord entity."""

    def test_create_memory_record(self) -> None:
        tenant_id = uuid4()
        agent_id = uuid4()

        record = MemoryRecord(
            id=uuid4(),
            tenant_id=tenant_id,
            agent_id=agent_id,
            scope=MemoryScope.DURABLE,
            namespace="test",
            content_ciphertext="encrypted_content",
            embedding=[0.1, 0.2, 0.3],
            metadata={"key": "value"},
            allowed_use_label=AllowedUseLabel.PUBLIC,
        )

        assert record.tenant_id == tenant_id
        assert record.agent_id == agent_id
        assert record.scope == MemoryScope.DURABLE
        assert record.namespace == "test"
        assert record.is_encrypted() is True

    def test_is_expired_false_when_no_expiry(self) -> None:
        record = MemoryRecord(
            id=uuid4(),
            tenant_id=uuid4(),
            agent_id=uuid4(),
            scope=MemoryScope.DURABLE,
            namespace="test",
            content_ciphertext="content",
        )
        assert record.is_expired() is False

    def test_is_expired_false_when_future(self) -> None:
        future = datetime.now(UTC) + timedelta(days=1)
        record = MemoryRecord(
            id=uuid4(),
            tenant_id=uuid4(),
            agent_id=uuid4(),
            scope=MemoryScope.DURABLE,
            namespace="test",
            content_ciphertext="content",
            expires_at=future,
        )
        assert record.is_expired() is False

    def test_is_expired_true_when_past(self) -> None:
        past = datetime.now(UTC) - timedelta(days=1)
        record = MemoryRecord(
            id=uuid4(),
            tenant_id=uuid4(),
            agent_id=uuid4(),
            scope=MemoryScope.DURABLE,
            namespace="test",
            content_ciphertext="content",
            expires_at=past,
        )
        assert record.is_expired() is True


class TestSessionSummary:
    """Tests for SessionSummary entity."""

    def test_create_session_summary(self) -> None:
        summary = SessionSummary(
            id=uuid4(),
            tenant_id=uuid4(),
            agent_id=uuid4(),
            session_id="session-123",
            summary_ciphertext="encrypted_summary",
            metadata={"message_count": 10},
        )

        assert summary.session_id == "session-123"
        assert summary.metadata["message_count"] == 10

    def test_touch_updates_timestamp(self) -> None:
        summary = SessionSummary(
            id=uuid4(),
            tenant_id=uuid4(),
            agent_id=uuid4(),
            session_id="session-123",
            summary_ciphertext="summary",
        )
        original = summary.updated_at
        summary.touch()
        assert summary.updated_at >= original


class TestMemoryRetentionPolicy:
    """Tests for MemoryRetentionPolicy entity."""

    def test_create_valid_policy(self) -> None:
        policy = MemoryRetentionPolicy(
            id=uuid4(),
            tenant_id=uuid4(),
            scope=MemoryScope.DURABLE,
            retention_days=30,
            max_records_per_tenant=10000,
            max_storage_mb=1000,
        )

        assert policy.retention_days == 30
        assert policy.max_records_per_tenant == 10000
        assert policy.max_storage_mb == 1000

    def test_invalid_retention_days_raises(self) -> None:
        with pytest.raises(ValueError, match="retention_days must be positive"):
            MemoryRetentionPolicy(
                id=uuid4(),
                tenant_id=uuid4(),
                scope=MemoryScope.DURABLE,
                retention_days=0,
            )

    def test_invalid_max_records_raises(self) -> None:
        with pytest.raises(ValueError, match="max_records_per_tenant must be positive"):
            MemoryRetentionPolicy(
                id=uuid4(),
                tenant_id=uuid4(),
                scope=MemoryScope.DURABLE,
                retention_days=30,
                max_records_per_tenant=-1,
            )

    def test_invalid_max_storage_raises(self) -> None:
        with pytest.raises(ValueError, match="max_storage_mb must be positive"):
            MemoryRetentionPolicy(
                id=uuid4(),
                tenant_id=uuid4(),
                scope=MemoryScope.DURABLE,
                retention_days=30,
                max_storage_mb=-1,
            )

    def test_calculate_expiry(self) -> None:
        policy = MemoryRetentionPolicy(
            id=uuid4(),
            tenant_id=uuid4(),
            scope=MemoryScope.DURABLE,
            retention_days=30,
        )
        expiry = policy.calculate_expiry()
        expected = datetime.now(UTC) + timedelta(days=30)
        # Allow small time difference
        assert abs((expiry - expected).total_seconds()) < 2

    def test_is_quota_exceeded_records(self) -> None:
        policy = MemoryRetentionPolicy(
            id=uuid4(),
            tenant_id=uuid4(),
            scope=MemoryScope.DURABLE,
            retention_days=30,
            max_records_per_tenant=100,
        )

        exceeded, reason = policy.is_quota_exceeded(100, 50)
        assert exceeded is True
        assert "Record count 100 exceeds limit 100" in reason

    def test_is_quota_exceeded_storage(self) -> None:
        policy = MemoryRetentionPolicy(
            id=uuid4(),
            tenant_id=uuid4(),
            scope=MemoryScope.DURABLE,
            retention_days=30,
            max_storage_mb=100,
        )

        exceeded, reason = policy.is_quota_exceeded(50, 100)
        assert exceeded is True
        assert "Storage 100MB exceeds limit 100MB" in reason

    def test_is_quota_not_exceeded(self) -> None:
        policy = MemoryRetentionPolicy(
            id=uuid4(),
            tenant_id=uuid4(),
            scope=MemoryScope.DURABLE,
            retention_days=30,
            max_records_per_tenant=1000,
            max_storage_mb=1000,
        )

        exceeded, reason = policy.is_quota_exceeded(100, 50)
        assert exceeded is False
        assert reason == ""


class TestMemoryAggregate:
    """Tests for MemoryAggregate."""

    def test_add_content(self) -> None:
        record = MemoryRecord(
            id=uuid4(),
            tenant_id=uuid4(),
            agent_id=uuid4(),
            scope=MemoryScope.DURABLE,
            namespace="test",
            content_ciphertext="",
        )
        aggregate = MemoryAggregate(record=record)

        aggregate.add_content("new content")
        assert record.content_ciphertext == "new content"

    def test_update_embedding(self) -> None:
        record = MemoryRecord(
            id=uuid4(),
            tenant_id=uuid4(),
            agent_id=uuid4(),
            scope=MemoryScope.DURABLE,
            namespace="test",
            content_ciphertext="content",
        )
        aggregate = MemoryAggregate(record=record)

        aggregate.update_embedding([0.1, 0.2, 0.3])
        assert record.embedding == [0.1, 0.2, 0.3]

    def test_set_expiry(self) -> None:
        record = MemoryRecord(
            id=uuid4(),
            tenant_id=uuid4(),
            agent_id=uuid4(),
            scope=MemoryScope.DURABLE,
            namespace="test",
            content_ciphertext="content",
        )
        aggregate = MemoryAggregate(record=record)

        expiry = datetime.now(UTC) + timedelta(days=7)
        aggregate.set_expiry(expiry)
        assert record.expires_at == expiry

    def test_mark_as_expired(self) -> None:
        record = MemoryRecord(
            id=uuid4(),
            tenant_id=uuid4(),
            agent_id=uuid4(),
            scope=MemoryScope.DURABLE,
            namespace="test",
            content_ciphertext="content",
        )
        aggregate = MemoryAggregate(record=record)

        aggregate.mark_as_expired()
        assert record.expires_at is not None
        assert record.is_expired() is True