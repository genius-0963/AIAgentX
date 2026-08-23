"""Memory retrieval service with semantic search and filtering."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID

from app.domain.entities.memory import (
    AllowedUseLabel,
    MemoryRecord,
    MemoryScope,
)
from app.domain.repositories.memory import MemoryRepository
from app.infrastructure.embeddings.base import EmbeddingService
from app.infrastructure.encryption.base import EncryptionService
from app.infrastructure.text.redactor import TextRedactor

if TYPE_CHECKING:
    from app.infrastructure.observability.logging import get_logger

logger = logging.getLogger(__name__)


class MemoryRetrievalService:
    """Service for retrieving memory with semantic search and filtering."""

    DEFAULT_LIMIT = 8
    MAX_LIMIT = 50
    DEFAULT_SIMILARITY_THRESHOLD = 0.7

    def __init__(
        self,
        memory_repository: MemoryRepository,
        embedding_service: EmbeddingService,
        encryption_service: EncryptionService,
        redactor: TextRedactor | None = None,
    ) -> None:
        """Initialize memory retrieval service.

        Args:
            memory_repository: Repository for memory operations
            embedding_service: Service for generating query embeddings
            encryption_service: Service for decryption
            redactor: Optional redactor for policy-based redaction
        """
        self._memory_repository = memory_repository
        self._embedding_service = embedding_service
        self._encryption_service = encryption_service
        self._redactor = redactor or TextRedactor()

    async def retrieve_memory(
        self,
        tenant_id: UUID,
        agent_id: UUID,
        query: str,
        namespace: str,
        scope: MemoryScope,
        limit: int = DEFAULT_LIMIT,
        session_id: str | None = None,
        metadata_filters: dict[str, object] | None = None,
        similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
    ) -> list[MemoryRecord]:
        """Retrieve memory using semantic search with filtering.

        Args:
            tenant_id: The tenant ID (mandatory for isolation)
            agent_id: The agent ID
            query: The search query text
            namespace: The namespace to search in
            scope: The memory scope to search
            limit: Maximum number of results (default 8, max 50)
            session_id: Optional session ID for session-scoped search
            metadata_filters: Optional metadata key-value filters
            similarity_threshold: Minimum similarity score (0.0 to 1.0)

        Returns:
            List of memory records with decrypted content and similarity scores
        """
        # Validate limit
        limit = min(max(1, limit), self.MAX_LIMIT)

        # Generate query embedding
        query_embedding = await self._embedding_service.generate_embedding(query, tenant_id)

        # Search by vector similarity
        results = await self._memory_repository.search_by_vector(
            tenant_id=tenant_id,
            agent_id=agent_id,
            query_embedding=query_embedding,
            namespace=namespace,
            scope=scope,
            limit=limit,
            session_id=session_id,
        )

        # Filter by similarity threshold
        filtered_results = [(record, score) for record, score in results if score >= similarity_threshold]

        # Apply metadata filters if provided
        if metadata_filters:
            filtered_results = self._apply_metadata_filters(filtered_results, metadata_filters)

        # Decrypt and redact results
        decrypted_records = await self._decrypt_and_redact_results(
            filtered_results, tenant_id, namespace
        )

        logger.info(
            "Memory retrieval completed",
            extra={
                "tenant_id": str(tenant_id),
                "agent_id": str(agent_id),
                "namespace": namespace,
                "scope": scope.value,
                "query_length": len(query),
                "results_count": len(decrypted_records),
                "limit": limit,
            },
        )

        return decrypted_records

    async def retrieve_by_metadata(
        self,
        tenant_id: UUID,
        agent_id: UUID,
        namespace: str,
        scope: MemoryScope,
        metadata_filters: dict[str, object],
        limit: int = 100,
    ) -> list[MemoryRecord]:
        """Retrieve memory records by metadata filters only.

        Args:
            tenant_id: The tenant ID (mandatory for isolation)
            agent_id: The agent ID
            namespace: The namespace to search in
            scope: The memory scope to search
            metadata_filters: Metadata key-value filters
            limit: Maximum number of results

        Returns:
            List of memory records with decrypted content
        """
        limit = min(max(1, limit), self.MAX_LIMIT)

        results = await self._memory_repository.search_by_metadata(
            tenant_id=tenant_id,
            agent_id=agent_id,
            namespace=namespace,
            scope=scope,
            metadata_filters=metadata_filters,
            limit=limit,
        )

        # Decrypt and redact results (no similarity scores)
        decrypted_records = []
        for record in results:
            decrypted = await self._decrypt_record(record, tenant_id, namespace)
            decrypted_records.append(decrypted)

        logger.info(
            "Metadata retrieval completed",
            extra={
                "tenant_id": str(tenant_id),
                "agent_id": str(agent_id),
                "namespace": namespace,
                "scope": scope.value,
                "filters": metadata_filters,
                "results_count": len(decrypted_records),
            },
        )

        return decrypted_records

    async def retrieve_by_session(
        self,
        tenant_id: UUID,
        agent_id: UUID,
        session_id: str,
        namespace: str,
        scope: MemoryScope,
        limit: int = DEFAULT_LIMIT,
    ) -> list[MemoryRecord]:
        """Retrieve memory records for a specific session.

        Args:
            tenant_id: The tenant ID (mandatory for isolation)
            agent_id: The agent ID
            session_id: The session ID
            namespace: The namespace to search in
            scope: The memory scope to search
            limit: Maximum number of results

        Returns:
            List of memory records with decrypted content
        """
        # Use a dummy query embedding for session retrieval
        # In practice, we might want a different approach for session-only retrieval
        dummy_embedding = [0.0] * self._embedding_service.embedding_dimension

        results = await self._memory_repository.search_by_vector(
            tenant_id=tenant_id,
            agent_id=agent_id,
            query_embedding=dummy_embedding,
            namespace=namespace,
            scope=scope,
            limit=limit,
            session_id=session_id,
        )

        # Filter by session_id (repository does this, but double-check)
        session_results = [(r, s) for r, s in results if r.session_id == session_id]

        decrypted_records = await self._decrypt_and_redact_results(
            session_results, tenant_id, namespace
        )

        logger.info(
            "Session retrieval completed",
            extra={
                "tenant_id": str(tenant_id),
                "agent_id": str(agent_id),
                "session_id": session_id,
                "namespace": namespace,
                "scope": scope.value,
                "results_count": len(decrypted_records),
            },
        )

        return decrypted_records

    async def get_memory_record(
        self,
        tenant_id: UUID,
        record_id: UUID,
    ) -> MemoryRecord | None:
        """Get a single memory record by ID.

        Args:
            tenant_id: The tenant ID (mandatory for isolation)
            record_id: The memory record ID

        Returns:
            Memory record with decrypted content or None if not found
        """
        record = await self._memory_repository.get(record_id)

        if not record:
            return None

        # Verify tenant isolation
        if record.tenant_id != tenant_id:
            logger.warning(
                "Tenant isolation violation attempt",
                extra={
                    "requested_tenant": str(tenant_id),
                    "record_tenant": str(record.tenant_id),
                    "record_id": str(record_id),
                },
            )
            return None

        return await self._decrypt_record(record, tenant_id, record.namespace)

    async def list_memory_records(
        self,
        tenant_id: UUID,
        agent_id: UUID,
        limit: int = 100,
        offset: int = 0,
    ) -> list[MemoryRecord]:
        """List memory records for a tenant and agent with pagination.

        Args:
            tenant_id: The tenant ID (mandatory for isolation)
            agent_id: The agent ID
            limit: Maximum number of results
            offset: Pagination offset

        Returns:
            List of memory records with decrypted content
        """
        limit = min(max(1, limit), self.MAX_LIMIT)

        records = await self._memory_repository.get_by_tenant_agent(
            tenant_id=tenant_id,
            agent_id=agent_id,
            limit=limit,
            offset=offset,
        )

        decrypted_records = []
        for record in records:
            decrypted = await self._decrypt_record(record, tenant_id, record.namespace)
            decrypted_records.append(decrypted)

        return decrypted_records

    def _apply_metadata_filters(
        self,
        results: list[tuple[MemoryRecord, float]],
        metadata_filters: dict[str, object],
    ) -> list[tuple[MemoryRecord, float]]:
        """Apply metadata filters to search results.

        Args:
            results: List of (record, similarity) tuples
            metadata_filters: Metadata key-value filters

        Returns:
            Filtered results
        """
        filtered = []
        for record, score in results:
            match = True
            for key, value in metadata_filters.items():
                if key not in record.metadata:
                    match = False
                    break
                if str(record.metadata[key]) != str(value):
                    match = False
                    break
            if match:
                filtered.append((record, score))
        return filtered

    async def _decrypt_and_redact_results(
        self,
        results: list[tuple[MemoryRecord, float]],
        tenant_id: UUID,
        namespace: str,
    ) -> list[MemoryRecord]:
        """Decrypt and redact a list of search results.

        Args:
            results: List of (record, similarity) tuples
            tenant_id: The tenant ID for decryption
            namespace: The namespace for policy lookup

        Returns:
            List of decrypted memory records with similarity in metadata
        """
        decrypted_records = []
        for record, similarity in results:
            decrypted = await self._decrypt_record(record, tenant_id, namespace)
            # Store similarity in metadata for downstream use
            decrypted.metadata["_similarity"] = similarity
            decrypted_records.append(decrypted)
        return decrypted_records

    async def _decrypt_record(
        self,
        record: MemoryRecord,
        tenant_id: UUID,
        namespace: str,
    ) -> MemoryRecord:
        """Decrypt and redact a single memory record.

        Args:
            record: The encrypted memory record
            tenant_id: The tenant ID for decryption
            namespace: The namespace for policy lookup

        Returns:
            Decrypted memory record
        """
        # Decrypt content
        decrypted_content = await self._encryption_service.decrypt(
            record.content_ciphertext, tenant_id
        )

        # Apply policy-based redaction
        if record.allowed_use_label != AllowedUseLabel.PUBLIC:
            redaction_result = await self._redactor.redact_based_on_policy(
                decrypted_content,
                record.allowed_use_label,
                tenant_id,
            )
            if redaction_result.was_redacted:
                decrypted_content = redaction_result.redacted_text

        # Create new record with decrypted content
        return MemoryRecord(
            id=record.id,
            tenant_id=record.tenant_id,
            agent_id=record.agent_id,
            scope=record.scope,
            namespace=record.namespace,
            content_ciphertext=decrypted_content,  # Now contains plaintext
            embedding=record.embedding,
            metadata=record.metadata,
            allowed_use_label=record.allowed_use_label,
            session_id=record.session_id,
            expires_at=record.expires_at,
            created_at=record.created_at,
            updated_at=record.updated_at,
        )