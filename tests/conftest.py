"""Shared test fixtures and configuration."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock
from uuid import uuid4

from app.domain.entities.memory import (
    MemoryRecord,
    MemoryScope,
    AllowedUseLabel,
    SessionSummary,
    MemoryRetentionPolicy,
)
from app.domain.repositories.memory import (
    MemoryRepository,
    SessionSummaryRepository,
    MemoryRetentionPolicyRepository,
)
from app.domain.repositories.outbox import OutboxRepository
from app.infrastructure.embeddings.base import EmbeddingService
from app.infrastructure.encryption.base import EncryptionService
from app.infrastructure.text.classifier import SensitiveDataClassifier
from app.infrastructure.text.chunker import TextChunker
from app.infrastructure.text.normalizer import TextNormalizer
from app.infrastructure.text.redactor import TextRedactor


@pytest.fixture
def tenant_id():
    return uuid4()


@pytest.fixture
def agent_id():
    return uuid4()


@pytest.fixture
def session_id():
    return "test-session-123"


@pytest.fixture
def mock_memory_repository():
    return AsyncMock(spec=MemoryRepository)


@pytest.fixture
def mock_session_summary_repository():
    return AsyncMock(spec=SessionSummaryRepository)


@pytest.fixture
def mock_retention_policy_repository():
    return AsyncMock(spec=MemoryRetentionPolicyRepository)


@pytest.fixture
def mock_outbox_repository():
    return AsyncMock(spec=OutboxRepository)


@pytest.fixture
def mock_embedding_service():
    service = AsyncMock(spec=EmbeddingService)
    service.generate_embedding.return_value = [0.1] * 1536
    service.embedding_dimension = 1536
    return service


@pytest.fixture
def mock_encryption_service():
    service = AsyncMock(spec=EncryptionService)
    service.encrypt.return_value = "encrypted_content"
    service.decrypt.return_value = "decrypted_content"
    return service


@pytest.fixture
def mock_classifier():
    return AsyncMock(spec=SensitiveDataClassifier)


@pytest.fixture
def mock_chunker():
    chunker = AsyncMock(spec=TextChunker)
    chunker.chunk_text.return_value = ["chunk1", "chunk2"]
    return chunker


@pytest.fixture
def mock_normalizer():
    normalizer = AsyncMock(spec=TextNormalizer)
    normalizer.normalize.return_value = "normalized content"
    normalizer.validate_size.return_value = True
    return normalizer


@pytest.fixture
def mock_redactor():
    return AsyncMock(spec=TextRedactor)


@pytest.fixture
def sample_memory_record(tenant_id, agent_id):
    return MemoryRecord(
        id=uuid4(),
        tenant_id=tenant_id,
        agent_id=agent_id,
        scope=MemoryScope.DURABLE,
        namespace="test",
        content_ciphertext="encrypted",
        embedding=[0.1] * 1536,
        metadata={"key": "value"},
        allowed_use_label=AllowedUseLabel.PUBLIC,
    )


@pytest.fixture
def sample_session_summary(tenant_id, agent_id):
    return SessionSummary(
        id=uuid4(),
        tenant_id=tenant_id,
        agent_id=agent_id,
        session_id="test-session",
        summary_ciphertext="summary",
        metadata={"message_count": 5},
    )


@pytest.fixture
def sample_retention_policy(tenant_id):
    return MemoryRetentionPolicy(
        id=uuid4(),
        tenant_id=tenant_id,
        scope=MemoryScope.DURABLE,
        retention_days=30,
        max_records_per_tenant=1000,
        max_storage_mb=100,
    )