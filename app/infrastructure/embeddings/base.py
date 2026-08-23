"""Embedding service base protocols."""

from __future__ import annotations

from typing import Protocol
from uuid import UUID


class EmbeddingError(Exception):
    """Exception raised when embedding generation fails."""

    pass


class EmbeddingProvider(Protocol):
    """Protocol for embedding generation providers."""

    async def generate_embedding(self, text: str, tenant_id: UUID) -> list[float]:
        """Generate embedding vector for text.

        Args:
            text: The text to embed
            tenant_id: The tenant ID for tracking/routing

        Returns:
            List of floats representing the embedding vector

        Raises:
            EmbeddingError: If embedding generation fails
        """
        ...

    async def generate_embeddings(
        self, texts: list[str], tenant_id: UUID
    ) -> list[list[float]]:
        """Generate embedding vectors for multiple texts.

        Args:
            texts: List of texts to embed
            tenant_id: The tenant ID for tracking/routing

        Returns:
            List of embedding vectors

        Raises:
            EmbeddingError: If embedding generation fails
        """
        ...

    @property
    def embedding_dimension(self) -> int:
        """Get the dimension of the embedding vectors."""
        ...


class EmbeddingService:
    """Service for managing embedding generation with fallback."""

    def __init__(
        self,
        primary_provider: EmbeddingProvider,
        fallback_provider: EmbeddingProvider | None = None,
    ) -> None:
        """Initialize embedding service.

        Args:
            primary_provider: Primary embedding provider
            fallback_provider: Optional fallback provider
        """
        self._primary = primary_provider
        self._fallback = fallback_provider

    async def generate_embedding(self, text: str, tenant_id: UUID) -> list[float]:
        """Generate embedding with fallback.

        Args:
            text: The text to embed
            tenant_id: The tenant ID for tracking/routing

        Returns:
            Embedding vector

        Raises:
            EmbeddingError: If all providers fail
        """
        try:
            return await self._primary.generate_embedding(text, tenant_id)
        except Exception as e:
            if self._fallback:
                try:
                    return await self._fallback.generate_embedding(text, tenant_id)
                except Exception:
                    pass
            raise EmbeddingError(f"Failed to generate embedding: {e}") from e

    async def generate_embeddings(
        self, texts: list[str], tenant_id: UUID
    ) -> list[list[float]]:
        """Generate embeddings with fallback.

        Args:
            texts: List of texts to embed
            tenant_id: The tenant ID for tracking/routing

        Returns:
            List of embedding vectors

        Raises:
            EmbeddingError: If all providers fail
        """
        try:
            return await self._primary.generate_embeddings(texts, tenant_id)
        except Exception as e:
            if self._fallback:
                try:
                    return await self._fallback.generate_embeddings(texts, tenant_id)
                except Exception:
                    pass
            raise EmbeddingError(f"Failed to generate embeddings: {e}") from e

    @property
    def embedding_dimension(self) -> int:
        """Get the embedding dimension."""
        return self._primary.embedding_dimension
