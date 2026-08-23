"""Unit tests for session memory service."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import UTC, datetime
from uuid import uuid4

from app.domain.entities.memory import MemoryScope, SessionSummary
from app.domain.repositories.memory import MemoryRepository, SessionSummaryRepository
from app.application.services.memory_write_service import MemoryWriteService
from app.infrastructure.cache.memory_cache import SessionMemoryCache
from app.application.services.session_memory_service import SessionMemoryService


class TestSessionMemoryService:
    """Tests for SessionMemoryService."""

    def setup_method(self) -> None:
        self.tenant_id = uuid4()
        self.agent_id = uuid4()
        self.session_id = "test-session-123"

        self.memory_repo = AsyncMock(spec=MemoryRepository)
        self.summary_repo = AsyncMock(spec=SessionSummaryRepository)
        self.write_service = AsyncMock(spec=MemoryWriteService)
        self.session_cache = AsyncMock(spec=SessionMemoryCache)

        self.service = SessionMemoryService(
            memory_repository=self.memory_repo,
            session_summary_repository=self.summary_repo,
            memory_write_service=self.write_service,
            session_cache=self.session_cache,
        )

    @pytest.mark.asyncio
    async def test_create_session_new(self) -> None:
        self.session_cache.get.return_value = None
        self.summary_repo.get_by_session_id.return_value = None

        meta = await self.service.create_session(
            tenant_id=self.tenant_id,
            agent_id=self.agent_id,
            session_id=self.session_id,
        )

        assert meta["session_id"] == self.session_id
        assert meta["tenant_id"] == str(self.tenant_id)
        assert meta["agent_id"] == str(self.agent_id)
        assert meta["message_count"] == 0

    @pytest.mark.asyncio
    async def test_create_session_from_cache(self) -> None:
        cached_meta = {
            "session_id": self.session_id,
            "tenant_id": str(self.tenant_id),
            "agent_id": str(self.agent_id),
            "message_count": 5,
            "metadata": {},
        }
        self.session_cache.get.return_value = cached_meta

        meta = await self.service.create_session(
            tenant_id=self.tenant_id,
            agent_id=self.agent_id,
            session_id=self.session_id,
        )

        assert meta == cached_meta

    @pytest.mark.asyncio
    async def test_get_session_meta_from_cache(self) -> None:
        cached_meta = {
            "session_id": self.session_id,
            "tenant_id": str(self.tenant_id),
            "agent_id": str(self.agent_id),
            "message_count": 5,
        }
        self.session_cache.get.return_value = cached_meta

        meta = await self.service.get_session_meta(
            tenant_id=self.tenant_id,
            agent_id=self.agent_id,
            session_id=self.session_id,
        )

        assert meta == cached_meta

    @pytest.mark.asyncio
    async def test_get_session_meta_from_db(self) -> None:
        self.session_cache.get.return_value = None

        summary = SessionSummary(
            id=uuid4(),
            tenant_id=self.tenant_id,
            agent_id=self.agent_id,
            session_id=self.session_id,
            summary_ciphertext="summary",
            metadata={"message_count": 10},
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        self.summary_repo.get_by_session_id.return_value = summary

        meta = await self.service.get_session_meta(
            tenant_id=self.tenant_id,
            agent_id=self.agent_id,
            session_id=self.session_id,
        )

        assert meta is not None
        assert meta["message_count"] == 10

    @pytest.mark.asyncio
    async def test_add_to_session(self) -> None:
        self.session_cache.get.return_value = None  # Force create
        self.session_cache.append_to_history.return_value = True
        self.session_cache.set.return_value = True

        meta = await self.service.add_to_session(
            tenant_id=self.tenant_id,
            agent_id=self.agent_id,
            session_id=self.session_id,
            role="user",
            content="Hello",
        )

        assert meta["message_count"] == 1
        self.session_cache.append_to_history.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_session_context_from_cache(self) -> None:
        history = [
            {"role": "user", "content": "Hello", "timestamp": datetime.now(UTC).isoformat()},
            {"role": "assistant", "content": "Hi!", "timestamp": datetime.now(UTC).isoformat()},
        ]
        self.session_cache.get_recent_history.return_value = history

        messages = await self.service.get_session_context(
            tenant_id=self.tenant_id,
            agent_id=self.agent_id,
            session_id=self.session_id,
            limit=10,
        )

        assert len(messages) == 2

    @pytest.mark.asyncio
    async def test_summarize_session(self) -> None:
        history = [
            {"role": "user", "content": "Question 1"},
            {"role": "assistant", "content": "Answer 1"},
        ]
        self.session_cache.get_all_history.return_value = history
        self.summary_repo.create.return_value = SessionSummary(
            id=uuid4(),
            tenant_id=self.tenant_id,
            agent_id=self.agent_id,
            session_id=self.session_id,
            summary_ciphertext="summary",
            metadata={"message_count": 2},
        )

        summary = await self.service.summarize_session(
            tenant_id=self.tenant_id,
            agent_id=self.agent_id,
            session_id=self.session_id,
        )

        assert summary is not None
        self.write_service.write_memory.assert_called_once()

    @pytest.mark.asyncio
    async def test_summarize_session_no_history(self) -> None:
        self.session_cache.get_all_history.return_value = []

        summary = await self.service.summarize_session(
            tenant_id=self.tenant_id,
            agent_id=self.agent_id,
            session_id=self.session_id,
        )

        assert summary is None

    @pytest.mark.asyncio
    async def test_end_session(self) -> None:
        self.session_cache.get.return_value = {"message_count": 5}
        self.session_cache.clear_session.return_value = 3
        self.service.summarize_session = AsyncMock(return_value=SessionSummary(
            id=uuid4(),
            tenant_id=self.tenant_id,
            agent_id=self.agent_id,
            session_id=self.session_id,
            summary_ciphertext="summary",
            metadata={},
        ))

        result = await self.service.end_session(
            tenant_id=self.tenant_id,
            agent_id=self.agent_id,
            session_id=self.session_id,
        )

        assert result["session_id"] == self.session_id
        assert result["summarized"] is True
        assert result["final_message_count"] == 5

    @pytest.mark.asyncio
    async def test_list_sessions(self) -> None:
        summaries = [
            SessionSummary(
                id=uuid4(),
                tenant_id=self.tenant_id,
                agent_id=self.agent_id,
                session_id=f"session-{i}",
                summary_ciphertext="summary",
                metadata={"message_count": i * 2},
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
            for i in range(3)
        ]
        self.summary_repo.list_by_agent.return_value = summaries

        sessions = await self.service.list_sessions(
            tenant_id=self.tenant_id,
            agent_id=self.agent_id,
            limit=10,
        )

        assert len(sessions) == 3
        assert sessions[0]["message_count"] == 0
        assert sessions[2]["message_count"] == 4

    @pytest.mark.asyncio
    async def test_delete_session(self) -> None:
        self.summary_repo.delete_by_session_id.return_value = True

        result = await self.service.delete_session(
            tenant_id=self.tenant_id,
            agent_id=self.agent_id,
            session_id=self.session_id,
        )

        assert result is True
        self.session_cache.clear_session.assert_called_once()