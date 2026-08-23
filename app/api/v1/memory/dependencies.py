"""Memory API dependencies."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.auth.middleware import get_current_tenant_id
from app.infrastructure.db.session import get_session
from app.infrastructure.cache.memory_cache import MemoryCacheManager
from app.infrastructure.cache.redis_client import get_redis_client
from app.infrastructure.embeddings.base import EmbeddingService
from app.infrastructure.embeddings.fake import FakeEmbeddingProvider
from app.infrastructure.embeddings.openai import OpenAIEmbeddingProvider
from app.infrastructure.encryption.aes_gcm import AESGCMEncryptionService
from app.infrastructure.encryption.tenant_key import TenantKeyManager
from app.infrastructure.text.chunker import TextChunker
from app.infrastructure.text.classifier import SensitiveDataClassifier
from app.infrastructure.text.normalizer import TextNormalizer
from app.infrastructure.text.redactor import TextRedactor
from app.application.services.memory_write_service import MemoryWriteService
from app.application.services.memory_retrieval_service import MemoryRetrievalService
from app.application.services.memory_cleanup_service import MemoryCleanupService
from app.application.services.session_memory_service import SessionMemoryService
from app.infrastructure.db.repositories.memory import (
    SQLMemoryRepository,
    SQLSessionSummaryRepository,
    SQLMemoryRetentionPolicyRepository,
)
from app.infrastructure.db.repositories.outbox import SQLOutboxRepository
from app.settings import get_settings

if TYPE_CHECKING:
    from app.domain.repositories.memory import (
        MemoryRepository,
        SessionSummaryRepository,
        MemoryRetentionPolicyRepository,
    )
    from app.infrastructure.embeddings.base import EmbeddingProvider
    from app.infrastructure.encryption.base import EncryptionService


# Embedding service dependency
async def get_embedding_service() -> EmbeddingService:
    """Get embedding service with configured providers."""
    settings = get_settings()

    # Primary provider
    if settings.openai_api_key:
        primary = OpenAIEmbeddingProvider.from_settings(settings)
    else:
        primary = FakeEmbeddingProvider.from_settings(settings)

    # Fallback provider (always fake for testing)
    fallback = FakeEmbeddingProvider.from_settings(settings)

    return EmbeddingService(primary_provider=primary, fallback_provider=fallback)


# Encryption service dependency
async def get_encryption_service() -> EncryptionService:
    """Get encryption service with tenant key manager."""
    settings = get_settings()
    key_manager = TenantKeyManager.from_secret(settings.encryption_master_secret)
    return AESGCMEncryptionService(key_manager=key_manager)


# Text processing dependencies
def get_text_normalizer() -> TextNormalizer:
    """Get text normalizer."""
    return TextNormalizer()


def get_text_chunker() -> TextChunker:
    """Get text chunker."""
    return TextChunker()


def get_classifier() -> SensitiveDataClassifier:
    """Get sensitive data classifier."""
    return SensitiveDataClassifier()


def get_redactor() -> TextRedactor:
    """Get text redactor."""
    return TextRedactor()


# Repository dependencies
async def get_memory_repository(
    session: AsyncSession = Depends(get_session),
) -> SQLMemoryRepository:
    """Get memory repository."""
    return SQLMemoryRepository(session)


async def get_session_summary_repository(
    session: AsyncSession = Depends(get_session),
) -> SQLSessionSummaryRepository:
    """Get session summary repository."""
    return SQLSessionSummaryRepository(session)


async def get_retention_policy_repository(
    session: AsyncSession = Depends(get_session),
) -> SQLMemoryRetentionPolicyRepository:
    """Get retention policy repository."""
    return SQLMemoryRetentionPolicyRepository(session)


# Service dependencies
async def get_outbox_repository(
    session: AsyncSession = Depends(get_session),
) -> SQLOutboxRepository:
    """Get outbox repository."""
    return SQLOutboxRepository(session)


# Service dependencies
async def get_memory_write_service(
    memory_repository: SQLMemoryRepository = Depends(get_memory_repository),
    retention_policy_repository: SQLMemoryRetentionPolicyRepository = Depends(get_retention_policy_repository),
    outbox_repository: SQLOutboxRepository = Depends(get_outbox_repository),
    embedding_service: EmbeddingService = Depends(get_embedding_service),
    encryption_service: EncryptionService = Depends(get_encryption_service),
    classifier: SensitiveDataClassifier = Depends(get_classifier),
    redactor: TextRedactor = Depends(get_redactor),
    chunker: TextChunker = Depends(get_text_chunker),
    normalizer: TextNormalizer = Depends(get_text_normalizer),
) -> MemoryWriteService:
    """Get memory write service."""
    return MemoryWriteService(
        memory_repository=memory_repository,
        retention_policy_repository=retention_policy_repository,
        outbox_repository=outbox_repository,
        embedding_service=embedding_service,
        encryption_service=encryption_service,
        classifier=classifier,
        redactor=redactor,
        chunker=chunker,
        normalizer=normalizer,
    )


async def get_memory_retrieval_service(
    memory_repository: SQLMemoryRepository = Depends(get_memory_repository),
    embedding_service: EmbeddingService = Depends(get_embedding_service),
    encryption_service: EncryptionService = Depends(get_encryption_service),
    redactor: TextRedactor = Depends(get_redactor),
) -> MemoryRetrievalService:
    """Get memory retrieval service."""
    return MemoryRetrievalService(
        memory_repository=memory_repository,
        embedding_service=embedding_service,
        encryption_service=encryption_service,
        redactor=redactor,
    )


async def get_memory_cleanup_service(
    memory_repository: SQLMemoryRepository = Depends(get_memory_repository),
    retention_policy_repository: SQLMemoryRetentionPolicyRepository = Depends(get_retention_policy_repository),
) -> MemoryCleanupService:
    """Get memory cleanup service."""
    return MemoryCleanupService(
        memory_repository=memory_repository,
        retention_policy_repository=retention_policy_repository,
    )


async def get_session_memory_service(
    memory_repository: SQLMemoryRepository = Depends(get_memory_repository),
    session_summary_repository: SQLSessionSummaryRepository = Depends(get_session_summary_repository),
    memory_write_service: MemoryWriteService = Depends(get_memory_write_service),
    redis_client = Depends(get_redis_client),
) -> SessionMemoryService:
    """Get session memory service."""
    session_cache = SessionMemoryCache(redis_client=redis_client)
    return SessionMemoryService(
        memory_repository=memory_repository,
        session_summary_repository=session_summary_repository,
        memory_write_service=memory_write_service,
        session_cache=session_cache,
    )


# Cache dependency
async def get_memory_cache_manager(
    redis_client = Depends(get_redis_client),
) -> MemoryCacheManager:
    """Get memory cache manager."""
    return MemoryCacheManager(redis_client=redis_client)


# Tenant ID from auth
async def get_tenant_id(request: Request) -> UUID:
    """Extract tenant ID from authenticated request."""
    tenant_id = get_current_tenant_id(request)
    if not tenant_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Tenant ID not found in request",
        )
    return tenant_id


# Agent ID from request (could be path param or header)
async def get_agent_id(request: Request) -> UUID:
    """Extract agent ID from request."""
    # Try path param first
    agent_id = request.path_params.get("agent_id")
    if agent_id:
        return UUID(agent_id)

    # Try header
    agent_id = request.headers.get("X-Agent-ID")
    if agent_id:
        return UUID(agent_id)

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Agent ID not provided",
    )