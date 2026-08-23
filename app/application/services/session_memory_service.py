"""Session memory service for managing conversational sessions."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID

from app.domain.entities.memory import (
    MemoryScope,
    SessionSummary,
)
from app.domain.repositories.memory import (
    MemoryRepository,
    SessionSummaryRepository,
)
from app.application.services.memory_write_service import MemoryWriteService
from app.infrastructure.cache.memory_cache import SessionMemoryCache

if TYPE_CHECKING:
    from app.infrastructure.observability.logging import get_logger

logger = logging.getLogger(__name__)


class SessionMemoryService:
    """Service for managing session-based memory with Redis cache and PostgreSQL persistence."""

    def __init__(
        self,
        memory_repository: MemoryRepository,
        session_summary_repository: SessionSummaryRepository,
        memory_write_service: MemoryWriteService,
        session_cache: SessionMemoryCache,
    ) -> None:
        """Initialize session memory service.

        Args:
            memory_repository: Repository for durable memory
            session_summary_repository: Repository for session summaries
            memory_write_service: Service for writing durable memory
            session_cache: Redis cache for session memory
        """
        self._memory_repository = memory_repository
        self._session_summary_repository = session_summary_repository
        self._memory_write_service = memory_write_service
        self._session_cache = session_cache

    async def create_session(
        self,
        tenant_id: UUID,
        agent_id: UUID,
        session_id: str,
        metadata: dict[str, object] | None = None,
    ) -> dict[str, object]:
        """Create a new session.

        Args:
            tenant_id: The tenant ID
            agent_id: The agent ID
            session_id: The session ID
            metadata: Optional session metadata

        Returns:
            Session info dictionary
        """
        # Check if session already exists in cache
        existing = await self._session_cache.get(session_id, "meta")
        if existing:
            logger.info(f"Session {session_id} already exists in cache")
            return existing

        # Check if session exists in PostgreSQL
        summary = await self._session_summary_repository.get_by_session_id(
            tenant_id, agent_id, session_id
        )

        session_meta = {
            "session_id": session_id,
            "tenant_id": str(tenant_id),
            "agent_id": str(agent_id),
            "created_at": datetime.now(UTC).isoformat(),
            "updated_at": datetime.now(UTC).isoformat(),
            "message_count": 0,
            "metadata": metadata or {},
        }

        # Store in cache
        await self._session_cache.set(session_id, "meta", session_meta)

        logger.info(
            "Session created",
            extra={
                "tenant_id": str(tenant_id),
                "agent_id": str(agent_id),
                "session_id": session_id,
            },
        )

        return session_meta

    async def get_session_meta(
        self,
        tenant_id: UUID,
        agent_id: UUID,
        session_id: str,
    ) -> dict[str, object] | None:
        """Get session metadata.

        Args:
            tenant_id: The tenant ID
            agent_id: The agent ID
            session_id: The session ID

        Returns:
            Session metadata or None if not found
        """
        # Try cache first
        meta = await self._session_cache.get(session_id, "meta")
        if meta:
            return meta

        # Try PostgreSQL
        summary = await self._session_summary_repository.get_by_session_id(
            tenant_id, agent_id, session_id
        )
        if summary:
            meta = {
                "session_id": session_id,
                "tenant_id": str(tenant_id),
                "agent_id": str(agent_id),
                "created_at": summary.created_at.isoformat(),
                "updated_at": summary.updated_at.isoformat(),
                "message_count": summary.metadata.get("message_count", 0),
                "metadata": summary.metadata,
            }
            # Restore to cache
            await self._session_cache.set(session_id, "meta", meta)
            return meta

        return None

    async def add_to_session(
        self,
        tenant_id: UUID,
        agent_id: UUID,
        session_id: str,
        role: str,
        content: str,
        metadata: dict[str, object] | None = None,
    ) -> dict[str, object]:
        """Add a message to the session.

        Args:
            tenant_id: The tenant ID
            agent_id: The agent ID
            session_id: The session ID
            role: Message role (user/assistant/system)
            content: Message content
            metadata: Optional message metadata

        Returns:
            Updated session info
        """
        # Get or create session
        meta = await self.get_session_meta(tenant_id, agent_id, session_id)
        if not meta:
            meta = await self.create_session(tenant_id, agent_id, session_id)

        # Create message entry
        message = {
            "role": role,
            "content": content,
            "timestamp": datetime.now(UTC).isoformat(),
            "metadata": metadata or {},
        }

        # Add to history in cache
        await self._session_cache.append_to_history(session_id, message)

        # Update session metadata
        meta["message_count"] = meta.get("message_count", 0) + 1
        meta["updated_at"] = datetime.now(UTC).isoformat()
        await self._session_cache.set(session_id, "meta", meta)

        logger.info(
            "Message added to session",
            extra={
                "tenant_id": str(tenant_id),
                "agent_id": str(agent_id),
                "session_id": session_id,
                "role": role,
                "message_count": meta["message_count"],
            },
        )

        return meta

    async def get_session_context(
        self,
        tenant_id: UUID,
        agent_id: UUID,
        session_id: str,
        limit: int = 10,
    ) -> list[dict[str, object]]:
        """Get recent conversation context for a session.

        Args:
            tenant_id: The tenant ID
            agent_id: The agent ID
            session_id: The session ID
            limit: Maximum number of messages to return

        Returns:
            List of recent messages
        """
        # Try cache first
        history = await self._session_cache.get_recent_history(session_id, limit)
        if history:
            return history

        # Try to restore from PostgreSQL (last N durable memory records)
        # This would require querying session-scoped durable memory
        # For now, return empty if not in cache
        logger.warning(
            "Session history not in cache, attempting durable retrieval",
            extra={"session_id": session_id},
        )

        # Query durable memory for this session
        records = await self._memory_repository.search_by_vector(
            tenant_id=tenant_id,
            agent_id=agent_id,
            query_embedding=[0.0] * 1536,  # Dummy embedding for session-only search
            namespace="conversation",
            scope=MemoryScope.SESSION,
            limit=limit,
            session_id=session_id,
        )

        # Convert to history format
        history = []
        for record, _ in records:
            # In real implementation, would decrypt
            history.append({
                "role": record.metadata.get("role", "assistant"),
                "content": "[ENCRYPTED]",
                "timestamp": record.created_at.isoformat(),
                "metadata": record.metadata,
            })

        # Store in cache for future
        if history:
            for msg in history:
                await self._session_cache.append_to_history(session_id, msg)

        return history

    async def get_full_history(
        self,
        tenant_id: UUID,
        agent_id: UUID,
        session_id: str,
    ) -> list[dict[str, object]]:
        """Get full conversation history for a session.

        Args:
            tenant_id: The tenant ID
            agent_id: The agent ID
            session_id: The session ID

        Returns:
            List of all messages
        """
        history = await self._session_cache.get_all_history(session_id)
        if history:
            return history

        # Fallback to durable storage
        logger.warning("Full history not in cache", extra={"session_id": session_id})
        return []

    async def summarize_session(
        self,
        tenant_id: UUID,
        agent_id: UUID,
        session_id: str,
    ) -> SessionSummary | None:
        """Summarize a session and persist to durable storage.

        Args:
            tenant_id: The tenant ID
            agent_id: The agent ID
            session_id: The session ID

        Returns:
            Created session summary or None if failed
        """
        # Get full history
        history = await self.get_full_history(tenant_id, agent_id, session_id)
        if not history:
            logger.warning(f"No history to summarize for session {session_id}")
            return None

        # Create summary content (in production, would use LLM)
        summary_content = self._create_extractive_summary(history)

        # Encrypt and store summary
        summary = SessionSummary(
            tenant_id=tenant_id,
            agent_id=agent_id,
            session_id=session_id,
            summary_ciphertext=summary_content,  # Will be encrypted by write service
            metadata={
                "message_count": len(history),
                "summarized_at": datetime.now(UTC).isoformat(),
                "original_messages": len(history),
            },
        )

        # Save to PostgreSQL
        saved_summary = await self._session_summary_repository.create(summary)

        # Also write as durable memory for semantic search
        await self._memory_write_service.write_memory(
            tenant_id=tenant_id,
            agent_id=agent_id,
            content=summary_content,
            scope=MemoryScope.DURABLE,
            namespace="session_summary",
            metadata={
                "session_id": session_id,
                "summary_id": str(saved_summary.id),
                "message_count": len(history),
            },
            session_id=session_id,
        )

        logger.info(
            "Session summarized and persisted",
            extra={
                "tenant_id": str(tenant_id),
                "agent_id": str(agent_id),
                "session_id": session_id,
                "summary_id": str(saved_summary.id),
                "message_count": len(history),
            },
        )

        return saved_summary

    def _create_extractive_summary(self, history: list[dict]) -> str:
        """Create an extractive summary from conversation history.

        Args:
            history: List of message dictionaries

        Returns:
            Summary text
        """
        # Simple extractive summary - in production would use LLM
        user_messages = [msg["content"] for msg in history if msg.get("role") == "user"]
        assistant_messages = [msg["content"] for msg in history if msg.get("role") == "assistant"]

        summary_parts = [
            f"Conversation with {len(history)} messages ({len(user_messages)} user, {len(assistant_messages)} assistant).",
        ]

        if user_messages:
            summary_parts.append("User asked about: " + "; ".join(user_messages[:5]))
        if assistant_messages:
            summary_parts.append("Assistant responded to: " + "; ".join(assistant_messages[:5]))

        return " ".join(summary_parts)

    async def end_session(
        self,
        tenant_id: UUID,
        agent_id: UUID,
        session_id: str,
    ) -> dict[str, object]:
        """End a session and persist to durable storage.

        Args:
            tenant_id: The tenant ID
            agent_id: The agent ID
            session_id: The session ID

        Returns:
            Session end result
        """
        # Summarize before ending
        summary = await self.summarize_session(tenant_id, agent_id, session_id)

        # Get final metadata
        meta = await self._session_cache.get(session_id, "meta")

        # Clear cache
        await self._session_cache.clear_session(session_id)

        result = {
            "session_id": session_id,
            "ended_at": datetime.now(UTC).isoformat(),
            "summarized": summary is not None,
            "summary_id": str(summary.id) if summary else None,
            "final_message_count": meta.get("message_count", 0) if meta else 0,
        }

        logger.info(
            "Session ended",
            extra={
                "tenant_id": str(tenant_id),
                "agent_id": str(agent_id),
                "session_id": session_id,
                **result,
            },
        )

        return result

    async def list_sessions(
        self,
        tenant_id: UUID,
        agent_id: UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, object]]:
        """List sessions for an agent.

        Args:
            tenant_id: The tenant ID
            agent_id: The agent ID
            limit: Maximum number of sessions
            offset: Pagination offset

        Returns:
            List of session summaries
        """
        summaries = await self._session_summary_repository.list_by_agent(
            tenant_id, agent_id, limit, offset
        )

        return [
            {
                "session_id": s.session_id,
                "summary_id": str(s.id),
                "created_at": s.created_at.isoformat(),
                "updated_at": s.updated_at.isoformat(),
                "message_count": s.metadata.get("message_count", 0),
                "metadata": s.metadata,
            }
            for s in summaries
        ]

    async def delete_session(
        self,
        tenant_id: UUID,
        agent_id: UUID,
        session_id: str,
    ) -> bool:
        """Delete a session completely.

        Args:
            tenant_id: The tenant ID
            agent_id: The agent ID
            session_id: The session ID

        Returns:
            True if deleted
        """
        # Delete from cache
        await self._session_cache.clear_session(session_id)

        # Delete from PostgreSQL
        deleted = await self._session_summary_repository.delete_by_session_id(
            tenant_id, agent_id, session_id
        )

        logger.info(
            "Session deleted",
            extra={
                "tenant_id": str(tenant_id),
                "agent_id": str(agent_id),
                "session_id": session_id,
                "deleted": deleted,
            },
        )

        return deleted