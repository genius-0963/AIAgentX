"""Unit tests for memory write service."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from app.domain.entities.memory import (
    MemoryRecord,
    MemoryScope,
    MemoryRetentionPolicy,
    AllowedUseLabel,
)
from app.domain.entities.outbox import OutboxEvent
from app.domain.repositories.memory import MemoryRepository, MemoryRetentionPolicyRepository
from app.domain.repositories.outbox import OutboxRepository
from app.infrastructure.embeddings.base import EmbeddingService
from app.infrastructure.encryption.base import EncryptionService
from app.infrastructure.text.classifier import ClassificationResult, SensitiveDataType
from app.infrastructure.text.chunker import TextChunker
from app.infrastructure.text.normalizer import TextNormalizer
from app.infrastructure.text.redactor import RedactionResult, TextRedactor
from app.application.services.memory_write_service import MemoryWriteService, MemoryQuotaExceededError


class TestMemoryWriteService:
    """Tests for MemoryWriteService."""

    def setup_method(self) -> None:
        self.tenant_id = uuid4()
        self.agent_id = uuid4()

        # Mock dependencies
        self.memory_repo = AsyncMock(spec=MemoryRepository)
        self.retention_repo = AsyncMock(spec=MemoryRetentionPolicyRepository)
        self.outbox_repo = AsyncMock(spec=OutboxRepository)
        self.embedding_service = AsyncMock(spec=EmbeddingService)
        self.encryption_service = AsyncMock(spec=EncryptionService)
        self.classifier = AsyncMock(spec=TextRedactor)  # Using TextRedactor as base for mock
        self.redactor = AsyncMock(spec=TextRedactor)
        self.chunker = MagicMock(spec=TextChunker)
        self.normalizer = MagicMock(spec=TextNormalizer)

        # Setup defaults
        self.normalizer.normalize.return_value = "normalized content"
        self.normalizer.validate_size.return_value = True
        self.retention_repo.get_by_tenant_scope.return_value = None  # No policy = no quota
        self.embedding_service.generate_embedding.return_value = [0.1] * 1536
        self.encryption_service.encrypt.return_value = "encrypted_content"
        self.chunker.chunk_text.return_value = ["chunk1", "chunk2"]

        # Classification mock
        self.classification = ClassificationResult(
            has_sensitive_data=False,
            sensitive_types=[],
            allowed_use_label=AllowedUseLabel.PUBLIC,
            confidence=1.0,
        )
        # We need to patch the classifier's classify method
        self.classifier_instance = AsyncMock()
        self.classifier_instance.classify.return_value = self.classification

        # Redaction mock
        self.redaction_result = RedactionResult(
            redacted_text="normalized content",
            redaction_count=0,
            was_redacted=False,
        )
        self.redactor_instance = AsyncMock()
        self.redactor_instance.redact.return_value = self.redaction_result

        self.service = MemoryWriteService(
            memory_repository=self.memory_repo,
            retention_policy_repository=self.retention_repo,
            outbox_repository=self.outbox_repo,
            embedding_service=self.embedding_service,
            encryption_service=self.encryption_service,
            classifier=self.classifier_instance,
            redactor=self.redactor_instance,
            chunker=self.chunker,
            normalizer=self.normalizer,
        )

    @pytest.mark.asyncio
    async def test_write_memory_basic(self) -> None:
        records = await self.service.write_memory(
            tenant_id=self.tenant_id,
            agent_id=self.agent_id,
            content="test content",
            scope=MemoryScope.DURABLE,
            namespace="test",
            metadata={"key": "value"},
        )

        assert len(records) == 2  # Two chunks
        assert all(isinstance(r, MemoryRecord) for r in records)
        assert records[0].tenant_id == self.tenant_id
        assert records[0].agent_id == self.agent_id
        assert records[0].scope == MemoryScope.DURABLE
        assert records[0].namespace == "test"

    @pytest.mark.asyncio
    async def test_write_memory_normalizes_input(self) -> None:
        await self.service.write_memory(
            tenant_id=self.tenant_id,
            agent_id=self.agent_id,
            content="  test   content  ",
            scope=MemoryScope.DURABLE,
            namespace="test",
            metadata={},
        )

        self.normalizer.normalize.assert_called_once_with("  test   content  ")

    @pytest.mark.asyncio
    async def test_write_memory_validates_size(self) -> None:
        await self.service.write_memory(
            tenant_id=self.tenant_id,
            agent_id=self.agent_id,
            content="test",
            scope=MemoryScope.DURABLE,
            namespace="test",
            metadata={},
        )

        self.normalizer.validate_size.assert_called_once()

    @pytest.mark.asyncio
    async def test_write_memory_classifies_content(self) -> None:
        await self.service.write_memory(
            tenant_id=self.tenant_id,
            agent_id=self.agent_id,
            content="test",
            scope=MemoryScope.DURABLE,
            namespace="test",
            metadata={},
        )

        self.classifier_instance.classify.assert_called_once()

    @pytest.mark.asyncio
    async def test_write_memory_redacts_content(self) -> None:
        await self.service.write_memory(
            tenant_id=self.tenant_id,
            agent_id=self.agent_id,
            content="test",
            scope=MemoryScope.DURABLE,
            namespace="test",
            metadata={},
        )

        self.redactor_instance.redact.assert_called_once()

    @pytest.mark.asyncio
    async def test_write_memory_chunks_content(self) -> None:
        await self.service.write_memory(
            tenant_id=self.tenant_id,
            agent_id=self.agent_id,
            content="test content that gets chunked",
            scope=MemoryScope.DURABLE,
            namespace="test",
            metadata={},
        )

        self.chunker.chunk_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_write_memory_generates_embeddings(self) -> None:
        await self.service.write_memory(
            tenant_id=self.tenant_id,
            agent_id=self.agent_id,
            content="test",
            scope=MemoryScope.DURABLE,
            namespace="test",
            metadata={},
        )

        assert self.embedding_service.generate_embedding.call_count == 2

    @pytest.mark.asyncio
    async def test_write_memory_encrypts_content(self) -> None:
        await self.service.write_memory(
            tenant_id=self.tenant_id,
            agent_id=self.agent_id,
            content="test",
            scope=MemoryScope.DURABLE,
            namespace="test",
            metadata={},
        )

        assert self.encryption_service.encrypt.call_count == 2

    @pytest.mark.asyncio
    async def test_write_memory_saves_records(self) -> None:
        await self.service.write_memory(
            tenant_id=self.tenant_id,
            agent_id=self.agent_id,
            content="test",
            scope=MemoryScope.DURABLE,
            namespace="test",
            metadata={},
        )

        assert self.memory_repo.create.call_count == 2

    @pytest.mark.asyncio
    async def test_write_memory_publishes_outbox_events(self) -> None:
        await self.service.write_memory(
            tenant_id=self.tenant_id,
            agent_id=self.agent_id,
            content="test",
            scope=MemoryScope.DURABLE,
            namespace="test",
            metadata={},
        )

        assert self.outbox_repo.create.call_count == 2

    @pytest.mark.asyncio
    async def test_write_memory_with_session_id(self) -> None:
        session_id = "session-123"
        records = await self.service.write_memory(
            tenant_id=self.tenant_id,
            agent_id=self.agent_id,
            content="test",
            scope=MemoryScope.SESSION,
            namespace="test",
            metadata={},
            session_id=session_id,
        )

        assert all(r.session_id == session_id for r in records)

    @pytest.mark.asyncio
    async def test_write_memory_with_sensitive_data(self) -> None:
        # Setup sensitive classification
        sensitive_classification = ClassificationResult(
            has_sensitive_data=True,
            sensitive_types=[SensitiveDataType.EMAIL],
            allowed_use_label=AllowedUseLabel.CONFIDENTIAL,
            confidence=0.8,
        )
        self.classifier_instance.classify.return_value = sensitive_classification

        sensitive_redaction = RedactionResult(
            redacted_text="Contact [REDACTED] for info",
            redaction_count=1,
            was_redacted=True,
        )
        self.redactor_instance.redact.return_value = sensitive_redaction

        records = await self.service.write_memory(
            tenant_id=self.tenant_id,
            agent_id=self.agent_id,
            content="Contact user@example.com for info",
            scope=MemoryScope.DURABLE,
            namespace="test",
            metadata={},
        )

        assert records[0].allowed_use_label == AllowedUseLabel.CONFIDENTIAL

    @pytest.mark.asyncio
    async def test_check_quota_exceeded(self) -> None:
        policy = MemoryRetentionPolicy(
            id=uuid4(),
            tenant_id=self.tenant_id,
            scope=MemoryScope.DURABLE,
            retention_days=30,
            max_records_per_tenant=10,
        )
        self.retention_repo.get_by_tenant_scope.return_value = policy
        self.memory_repo.count_by_tenant.return_value = 10
        self.memory_repo.get_storage_size_bytes.return_value = 0

        with pytest.raises(MemoryQuotaExceededError):
            await self.service.write_memory(
                tenant_id=self.tenant_id,
                agent_id=self.agent_id,
                content="test",
                scope=MemoryScope.DURABLE,
                namespace="test",
                metadata={},
            )

    @pytest.mark.asyncio
    async def test_calculate_expiry_with_policy(self) -> None:
        policy = MemoryRetentionPolicy(
            id=uuid4(),
            tenant_id=self.tenant_id,
            scope=MemoryScope.DURABLE,
            retention_days=30,
        )
        self.retention_repo.get_by_tenant_scope.return_value = policy

        records = await self.service.write_memory(
            tenant_id=self.tenant_id,
            agent_id=self.agent_id,
            content="test",
            scope=MemoryScope.DURABLE,
            namespace="test",
            metadata={},
        )

        assert records[0].expires_at is not None

    @pytest.mark.asyncio
    async def test_calculate_expiry_defaults(self) -> None:
        # No policy
        self.retention_repo.get_by_tenant_scope.return_value = None

        records_ephemeral = await self.service.write_memory(
            tenant_id=self.tenant_id,
            agent_id=self.agent_id,
            content="test",
            scope=MemoryScope.EPHEMERAL,
            namespace="test",
            metadata={},
        )
        assert records_ephemeral[0].expires_at is not None

        records_session = await self.service.write_memory(
            tenant_id=self.tenant_id,
            agent_id=self.agent_id,
            content="test",
            scope=MemoryScope.SESSION,
            namespace="test",
            metadata={},
        )
        assert records_session[0].expires_at is not None

        records_durable = await self.service.write_memory(
            tenant_id=self.tenant_id,
            agent_id=self.agent_id,
            content="test",
            scope=MemoryScope.DURABLE,
            namespace="test",
            metadata={},
        )
        # Durable has no default expiry
        assert records_durable[0].expires_at is None