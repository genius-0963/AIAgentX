"""Memory write service with validation and redaction pipeline."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING
from uuid import UUID

from app.domain.entities.memory import (
    AllowedUseLabel,
    MemoryRecord,
    MemoryScope,
    MemoryRetentionPolicy,
)
from app.domain.entities.outbox import OutboxEvent
from app.domain.repositories.memory import MemoryRepository, MemoryRetentionPolicyRepository
from app.domain.repositories.outbox import OutboxRepository
from app.infrastructure.embeddings.base import EmbeddingService
from app.infrastructure.encryption.base import EncryptionService
from app.infrastructure.text.classifier import ClassificationResult, SensitiveDataClassifier
from app.infrastructure.text.chunker import TextChunker
from app.infrastructure.text.normalizer import TextNormalizer
from app.infrastructure.text.redactor import RedactionResult, TextRedactor

if TYPE_CHECKING:
    from app.infrastructure.observability.logging import get_logger

logger = logging.getLogger(__name__)


class MemoryWriteService:
    """Service for writing memory with validation and redaction pipeline."""

    def __init__(
        self,
        memory_repository: MemoryRepository,
        retention_policy_repository: MemoryRetentionPolicyRepository,
        outbox_repository: OutboxRepository,
        embedding_service: EmbeddingService,
        encryption_service: EncryptionService,
        classifier: SensitiveDataClassifier | None = None,
        redactor: TextRedactor | None = None,
        chunker: TextChunker | None = None,
        normalizer: TextNormalizer | None = None,
    ) -> None:
        """Initialize memory write service.

        Args:
            memory_repository: Repository for memory operations
            retention_policy_repository: Repository for retention policies
            outbox_repository: Repository for outbox events
            embedding_service: Service for generating embeddings
            encryption_service: Service for encryption
            classifier: Optional classifier for sensitive data
            redactor: Optional redactor for sensitive data
            chunker: Optional chunker for text splitting
            normalizer: Optional normalizer for text
        """
        self._memory_repository = memory_repository
        self._retention_policy_repository = retention_policy_repository
        self._outbox_repository = outbox_repository
        self._embedding_service = embedding_service
        self._encryption_service = encryption_service
        self._classifier = classifier or SensitiveDataClassifier()
        self._redactor = redactor or TextRedactor()
        self._chunker = chunker or TextChunker()
        self._normalizer = normalizer or TextNormalizer()

    async def write_memory(
        self,
        tenant_id: UUID,
        agent_id: UUID,
        content: str,
        scope: MemoryScope,
        namespace: str,
        metadata: dict[str, object],
        session_id: str | None = None,
    ) -> list[MemoryRecord]:
        """Write memory with full validation and redaction pipeline.

        Args:
            tenant_id: The tenant ID
            agent_id: The agent ID
            content: The content to store
            scope: The memory scope
            namespace: The namespace for organization
            metadata: Additional metadata
            session_id: Optional session ID for session memory

        Returns:
            List of created memory records (one per chunk)

        Raises:
            ValueError: If validation fails
            MemoryQuotaExceededError: If tenant quota exceeded
        """
        # Step 1: Normalize input
        normalized_content = self._normalizer.normalize(content)
        self._normalizer.validate_size(normalized_content)

        # Step 2: Check retention policy and quota
        await self._check_quota(tenant_id, scope)

        # Step 3: Classify and redact sensitive data
        classification = await self._classifier.classify(normalized_content, tenant_id)
        redaction_result = await self._redactor.redact(normalized_content, classification, tenant_id)

        processed_content = redaction_result.redacted_text

        # Step 4: Chunk content
        chunks = self._chunker.chunk_text(processed_content)

        # Step 5: Calculate expiry based on retention policy
        expires_at = await self._calculate_expiry(tenant_id, scope)

        # Step 6: Process each chunk
        records = []
        for chunk in chunks:
            # Generate embedding
            embedding = await self._embedding_service.generate_embedding(chunk, tenant_id)

            # Encrypt content
            ciphertext = await self._encryption_service.encrypt(chunk, tenant_id)

            # Create memory record
            record = MemoryRecord(
                tenant_id=tenant_id,
                agent_id=agent_id,
                scope=scope,
                namespace=namespace,
                content_ciphertext=ciphertext,
                embedding=embedding,
                metadata=metadata,
                allowed_use_label=classification.allowed_use_label,
                session_id=session_id,
                expires_at=expires_at,
            )

            # Store record
            saved_record = await self._memory_repository.create(record)
            records.append(saved_record)

            # Publish outbox event
            await self._publish_memory_written_event(saved_record, chunk, classification, redaction_result)

        logger.info(
            "Memory write completed",
            extra={
                "tenant_id": str(tenant_id),
                "agent_id": str(agent_id),
                "chunk_count": len(chunks),
                "was_redacted": redaction_result.was_redacted,
            },
        )

        return records

    async def _publish_memory_written_event(
        self,
        record: MemoryRecord,
        chunk: str,
        classification,
        redaction_result,
    ) -> None:
        """Publish memory written event to outbox."""
        event = OutboxEvent.create(
            event_type="memory.written",
            aggregate_id=str(record.id),
            aggregate_type="MemoryRecord",
            payload={
                "tenant_id": str(record.tenant_id),
                "agent_id": str(record.agent_id),
                "scope": record.scope.value,
                "namespace": record.namespace,
                "session_id": record.session_id,
                "allowed_use_label": record.allowed_use_label.value,
                "chunk_length": len(chunk),
                "was_redacted": redaction_result.was_redacted,
                "redaction_count": redaction_result.redaction_count,
                "sensitive_types": [t.value for t in classification.sensitive_types],
            },
        )

        await self._outbox_repository.create(event)

        logger.info(
            "Memory written event published",
            extra={
                "event_id": str(event.id),
                "tenant_id": str(record.tenant_id),
                "record_id": str(record.id),
            },
        )

    async def _check_quota(self, tenant_id: UUID, scope: MemoryScope) -> None:
        """Check if tenant quota allows writing memory.

        Args:
            tenant_id: The tenant ID
            scope: The memory scope

        Raises:
            MemoryQuotaExceededError: If quota exceeded
        """
        policy = await self._retention_policy_repository.get_by_tenant_scope(tenant_id, scope)

        if not policy:
            # Use default policy if none exists
            return

        # Check current usage
        current_count = await self._memory_repository.count_by_tenant(tenant_id, scope)
        current_storage = await self._memory_repository.get_storage_size_bytes(tenant_id)
        current_storage_mb = current_storage / (1024 * 1024)

        # Check quota
        is_exceeded, reason = policy.is_quota_exceeded(current_count, current_storage_mb)

        if is_exceeded:
            raise MemoryQuotaExceededError(f"Memory quota exceeded: {reason}")

    async def _calculate_expiry(self, tenant_id: UUID, scope: MemoryScope) -> datetime | None:
        """Calculate expiry time based on retention policy.

        Args:
            tenant_id: The tenant ID
            scope: The memory scope

        Returns:
            Expiry datetime or None for no expiry
        """
        policy = await self._retention_policy_repository.get_by_tenant_scope(tenant_id, scope)

        if not policy:
            # Default expiry based on scope
            if scope == MemoryScope.EPHEMERAL:
                return datetime.now(UTC) + timedelta(hours=24)
            elif scope == MemoryScope.SESSION:
                return datetime.now(UTC) + timedelta(days=7)
            else:
                return None  # Durable has no default expiry

        return policy.calculate_expiry()


class MemoryQuotaExceededError(Exception):
    """Exception raised when memory quota is exceeded."""

    pass
