"""Memory repository protocols."""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from app.domain.entities.memory import (
    AllowedUseLabel,
    MemoryRecord,
    MemoryRetentionPolicy,
    MemoryScope,
    SessionSummary,
)


class MemoryRepository(Protocol):
    """Repository for memory record operations."""

    async def create(self, record: MemoryRecord) -> MemoryRecord:
        """Create a new memory record."""
        ...

    async def get(self, record_id: UUID) -> MemoryRecord | None:
        """Get memory record by ID."""
        ...

    async def get_by_tenant_agent(
        self,
        tenant_id: UUID,
        agent_id: UUID,
        limit: int = 100,
        offset: int = 0,
    ) -> list[MemoryRecord]:
        """Get memory records for a tenant and agent."""
        ...

    async def search_by_vector(
        self,
        tenant_id: UUID,
        agent_id: UUID,
        query_embedding: list[float],
        namespace: str,
        scope: MemoryScope,
        limit: int = 8,
        session_id: str | None = None,
    ) -> list[tuple[MemoryRecord, float]]:
        """Search memory records by vector similarity.

        Returns:
            List of (record, similarity_score) tuples
        """
        ...

    async def search_by_metadata(
        self,
        tenant_id: UUID,
        agent_id: UUID,
        namespace: str,
        scope: MemoryScope,
        metadata_filters: dict[str, object],
        limit: int = 100,
    ) -> list[MemoryRecord]:
        """Search memory records by metadata filters."""
        ...

    async def update(self, record: MemoryRecord) -> MemoryRecord:
        """Update an existing memory record."""
        ...

    async def delete(self, record_id: UUID) -> bool:
        """Delete a memory record."""
        ...

    async def delete_expired(self, tenant_id: UUID) -> int:
        """Delete expired memory records for a tenant.

        Returns:
            Number of records deleted
        """
        ...

    async def count_by_tenant(
        self,
        tenant_id: UUID,
        scope: MemoryScope | None = None,
    ) -> int:
        """Count memory records for a tenant."""
        ...

    async def get_storage_size_bytes(self, tenant_id: UUID) -> int:
        """Get total storage size in bytes for a tenant."""
        ...


class SessionSummaryRepository(Protocol):
    """Repository for session summary operations."""

    async def create(self, summary: SessionSummary) -> SessionSummary:
        """Create a new session summary."""
        ...

    async def get(self, summary_id: UUID) -> SessionSummary | None:
        """Get session summary by ID."""
        ...

    async def get_by_session_id(
        self,
        tenant_id: UUID,
        agent_id: UUID,
        session_id: str,
    ) -> SessionSummary | None:
        """Get session summary by session ID."""
        ...

    async def update(self, summary: SessionSummary) -> SessionSummary:
        """Update an existing session summary."""
        ...

    async def delete(self, summary_id: UUID) -> bool:
        """Delete a session summary."""
        ...

    async def delete_by_session_id(
        self,
        tenant_id: UUID,
        agent_id: UUID,
        session_id: str,
    ) -> bool:
        """Delete session summary by session ID."""
        ...

    async def list_by_agent(
        self,
        tenant_id: UUID,
        agent_id: UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> list[SessionSummary]:
        """List session summaries for an agent."""
        ...


class MemoryRetentionPolicyRepository(Protocol):
    """Repository for memory retention policy operations."""

    async def create(self, policy: MemoryRetentionPolicy) -> MemoryRetentionPolicy:
        """Create a new retention policy."""
        ...

    async def get(self, policy_id: UUID) -> MemoryRetentionPolicy | None:
        """Get retention policy by ID."""
        ...

    async def get_by_tenant_scope(
        self,
        tenant_id: UUID,
        scope: MemoryScope,
    ) -> MemoryRetentionPolicy | None:
        """Get retention policy by tenant and scope."""
        ...

    async def update(self, policy: MemoryRetentionPolicy) -> MemoryRetentionPolicy:
        """Update an existing retention policy."""
        ...

    async def delete(self, policy_id: UUID) -> bool:
        """Delete a retention policy."""
        ...

    async def list_by_tenant(
        self,
        tenant_id: UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> list[MemoryRetentionPolicy]:
        """List retention policies for a tenant."""
        ...

    async def upsert(self, policy: MemoryRetentionPolicy) -> MemoryRetentionPolicy:
        """Create or update a retention policy."""
        ...
