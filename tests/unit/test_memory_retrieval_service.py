"""Unit tests for memory retrieval service."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from app.domain.entities.memory import (
    MemoryRecord,
    MemoryScope,
    AllowedUseLabel,
)
from app.domain.repositories.memory import MemoryRepository
from app.infrastructure.embeddings.base import EmbeddingService
from app.infrastructure.encryption.base import EncryptionService
from app.infrastructure.text.redactor import TextRedactor
from app.application.services.memory_retrieval_service import MemoryRetrievalService


class TestMemoryRetrievalService:
    """Tests for MemoryRetrievalService."""

    def setup_method(self) -> None:
        self.tenant_id = uuid4()
        self.agent_id = uuid4()

        # Mock dependencies
        self.memory_repo = AsyncMock(spec=MemoryRepository)
        self.embedding_service = AsyncMock(spec=EmbeddingService)
        self.encryption_service = AsyncMock(spec=EncryptionService)
        self.redactor = AsyncMock(spec=TextRedactor)

        # Setup defaults
        self.embedding_service.generate_embedding.return_value = [0.1] * 1536
        self.encryption_service.decrypt.return_value = "decrypted content"

        self.service = MemoryRetrievalService(
            memory_repository=self.memory_repo,
            embedding_service=self.embedding_service,
            encryption_service=self.encryption_service,
            redactor=self.redactor,
        )

    @pytest.mark.asyncio
    async def test_retrieve_memory_basic(self) -> None:
        # Mock repository results
        record = MemoryRecord(
            id=uuid4(),
            tenant_id=self.tenant_id,
            agent_id=self.agent_id,
            scope=MemoryScope.DURABLE,
            namespace="test",
            content_ciphertext="encrypted",
            metadata={"key": "value"},
            allowed_use_label=AllowedUseLabel.PUBLIC,
        )
        self.memory_repo.search_by_vector.return_value = [(record, 0.9)]

        results = await self.service.retrieve_memory(
            tenant_id=self.tenant_id,
            agent_id=self.agent_id,
            query="test query",
            namespace="test",
            scope=MemoryScope.DURABLE,
        )

        assert len(results) == 1
        assert results[0].content_ciphertext == "decrypted content"
        assert results[0].metadata["_similarity"] == 0.9

    @pytest.mark.asyncio
    async def test_retrieve_memory_generates_query_embedding(self) -> None:
        record = MemoryRecord(
            id=uuid4(),
            tenant_id=self.tenant_id,
            agent_id=self.agent_id,
            scope=MemoryScope.DURABLE,
            namespace="test",
            content_ciphertext="encrypted",
            metadata={},
            allowed_use_label=AllowedUseLabel.PUBLIC,
        )
        self.memory_repo.search_by_vector.return_value = [(record, 0.9)]

        await self.service.retrieve_memory(
            tenant_id=self.tenant_id,
            agent_id=self.agent_id,
            query="test query",
            namespace="test",
            scope=MemoryScope.DURABLE,
        )

        self.embedding_service.generate_embedding.assert_called_once_with("test query", self.tenant_id)

    @pytest.mark.asyncio
    async def test_retrieve_memory_respects_limit(self) -> None:
        records = [
            MemoryRecord(
                id=uuid4(),
                tenant_id=self.tenant_id,
                agent_id=self.agent_id,
                scope=MemoryScope.DURABLE,
                namespace="test",
                content_ciphertext="encrypted",
                metadata={},
                allowed_use_label=AllowedUseLabel.PUBLIC,
            )
            for _ in range(10)
        ]
        self.memory_repo.search_by_vector.return_value = [(r, 0.9) for r in records]

        results = await self.service.retrieve_memory(
            tenant_id=self.tenant_id,
            agent_id=self.agent_id,
            query="test",
            namespace="test",
            scope=MemoryScope.DURABLE,
            limit=5,
        )

        assert len(results) == 5

    @pytest.mark.asyncio
    async def test_retrieve_memory_enforces_max_limit(self) -> None:
        records = [
            MemoryRecord(
                id=uuid4(),
                tenant_id=self.tenant_id,
                agent_id=self.agent_id,
                scope=MemoryScope.DURABLE,
                namespace="test",
                content_ciphertext="encrypted",
                metadata={},
                allowed_use_label=AllowedUseLabel.PUBLIC,
            )
            for _ in range(100)
        ]
        self.memory_repo.search_by_vector.return_value = [(r, 0.9) for r in records]

        results = await self.service.retrieve_memory(
            tenant_id=self.tenant_id,
            agent_id=self.agent_id,
            query="test",
            namespace="test",
            scope=MemoryScope.DURABLE,
            limit=100,  # Over max of 50
        )

        assert len(results) == 50

    @pytest.mark.asyncio
    async def test_retrieve_memory_filters_by_similarity_threshold(self) -> None:
        record_high = MemoryRecord(
            id=uuid4(),
            tenant_id=self.tenant_id,
            agent_id=self.agent_id,
            scope=MemoryScope.DURABLE,
            namespace="test",
            content_ciphertext="encrypted",
            metadata={},
            allowed_use_label=AllowedUseLabel.PUBLIC,
        )
        record_low = MemoryRecord(
            id=uuid4(),
            tenant_id=self.tenant_id,
            agent_id=self.agent_id,
            scope=MemoryScope.DURABLE,
            namespace="test",
            content_ciphertext="encrypted",
            metadata={},
            allowed_use_label=AllowedUseLabel.PUBLIC,
        )
        self.memory_repo.search_by_vector.return_value = [
            (record_high, 0.9),
            (record_low, 0.5),
        ]

        results = await self.service.retrieve_memory(
            tenant_id=self.tenant_id,
            agent_id=self.agent_id,
            query="test",
            namespace="test",
            scope=MemoryScope.DURABLE,
            similarity_threshold=0.7,
        )

        assert len(results) == 1
        assert results[0].metadata["_similarity"] == 0.9

    @pytest.mark.asyncio
    async def test_retrieve_memory_with_session_id(self) -> None:
        record = MemoryRecord(
            id=uuid4(),
            tenant_id=self.tenant_id,
            agent_id=self.agent_id,
            scope=MemoryScope.SESSION,
            namespace="test",
            content_ciphertext="encrypted",
            metadata={},
            allowed_use_label=AllowedUseLabel.PUBLIC,
            session_id="session-123",
        )
        self.memory_repo.search_by_vector.return_value = [(record, 0.9)]

        results = await self.service.retrieve_memory(
            tenant_id=self.tenant_id,
            agent_id=self.agent_id,
            query="test",
            namespace="test",
            scope=MemoryScope.SESSION,
            session_id="session-123",
        )

        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_retrieve_memory_decrypts_content(self) -> None:
        record = MemoryRecord(
            id=uuid4(),
            tenant_id=self.tenant_id,
            agent_id=self.agent_id,
            scope=MemoryScope.DURABLE,
            namespace="test",
            content_ciphertext="encrypted",
            metadata={},
            allowed_use_label=AllowedUseLabel.PUBLIC,
        )
        self.memory_repo.search_by_vector.return_value = [(record, 0.9)]

        results = await self.service.retrieve_memory(
            tenant_id=self.tenant_id,
            agent_id=self.agent_id,
            query="test",
            namespace="test",
            scope=MemoryScope.DURABLE,
        )

        self.encryption_service.decrypt.assert_called_once_with("encrypted", self.tenant_id)

    @pytest.mark.asyncio
    async def test_retrieve_memory_applies_redaction_policy(self) -> None:
        record = MemoryRecord(
            id=uuid4(),
            tenant_id=self.tenant_id,
            agent_id=self.agent_id,
            scope=MemoryScope.DURABLE,
            namespace="test",
            content_ciphertext="encrypted",
            metadata={},
            allowed_use_label=AllowedUseLabel.CONFIDENTIAL,
        )
        self.memory_repo.search_by_vector.return_value = [(record, 0.9)]
        self.redactor.redact_based_on_policy.return_value = MagicMock(
            redacted_text="[REDACTED]",
            was_redacted=True,
        )

        results = await self.service.retrieve_memory(
            tenant_id=self.tenant_id,
            agent_id=self.agent_id,
            query="test",
            namespace="test",
            scope=MemoryScope.DURABLE,
        )

        self.redactor.redact_based_on_policy.assert_called_once()

    @pytest.mark.asyncio
    async def test_retrieve_by_metadata(self) -> None:
        records = [
            MemoryRecord(
                id=uuid4(),
                tenant_id=self.tenant_id,
                agent_id=self.agent_id,
                scope=MemoryScope.DURABLE,
                namespace="test",
                content_ciphertext="encrypted",
                metadata={"category": "important"},
                allowed_use_label=AllowedUseLabel.PUBLIC,
            )
        ]
        self.memory_repo.search_by_metadata.return_value = records

        results = await self.service.retrieve_by_metadata(
            tenant_id=self.tenant_id,
            agent_id=self.agent_id,
            namespace="test",
            scope=MemoryScope.DURABLE,
            metadata_filters={"category": "important"},
        )

        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_retrieve_by_session(self) -> None:
        record = MemoryRecord(
            id=uuid4(),
            tenant_id=self.tenant_id,
            agent_id=self.agent_id,
            scope=MemoryScope.SESSION,
            namespace="test",
            content_ciphertext="encrypted",
            metadata={},
            allowed_use_label=AllowedUseLabel.PUBLIC,
            session_id="session-123",
        )
        self.memory_repo.search_by_vector.return_value = [(record, 0.9)]

        results = await self.service.retrieve_by_session(
            tenant_id=self.tenant_id,
            agent_id=self.agent_id,
            session_id="session-123",
            namespace="test",
            scope=MemoryScope.SESSION,
        )

        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_get_memory_record(self) -> None:
        record = MemoryRecord(
            id=uuid4(),
            tenant_id=self.tenant_id,
            agent_id=self.agent_id,
            scope=MemoryScope.DURABLE,
            namespace="test",
            content_ciphertext="encrypted",
            metadata={},
            allowed_use_label=AllowedUseLabel.PUBLIC,
        )
        self.memory_repo.get.return_value = record

        result = await self.service.get_memory_record(
            tenant_id=self.tenant_id,
            record_id=record.id,
        )

        assert result is not None
        assert result.id == record.id

    @pytest.mark.asyncio
    async def test_get_memory_record_enforces_tenant_isolation(self) -> None:
        record = MemoryRecord(
            id=uuid4(),
            tenant_id=uuid4(),  # Different tenant!
            agent_id=self.agent_id,
            scope=MemoryScope.DURABLE,
            namespace="test",
            content_ciphertext="encrypted",
            metadata={},
            allowed_use_label=AllowedUseLabel.PUBLIC,
        )
        self.memory_repo.get.return_value = record

        result = await self.service.get_memory_record(
            tenant_id=self.tenant_id,
            record_id=record.id,
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_list_memory_records(self) -> None:
        records = [
            MemoryRecord(
                id=uuid4(),
                tenant_id=self.tenant_id,
                agent_id=self.agent_id,
                scope=MemoryScope.DURABLE,
                namespace="test",
                content_ciphertext="encrypted",
                metadata={},
                allowed_use_label=AllowedUseLabel.PUBLIC,
            )
            for _ in range(5)
        ]
        self.memory_repo.get_by_tenant_agent.return_value = records

        results = await self.service.list_memory_records(
            tenant_id=self.tenant_id,
            agent_id=self.agent_id,
            limit=10,
            offset=0,
        )

        assert len(results) == 5