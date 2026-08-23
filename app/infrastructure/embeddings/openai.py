"""OpenAI embedding provider implementation."""

from __future__ import annotations

import logging
from uuid import UUID

from openai import AsyncOpenAI

from app.infrastructure.embeddings.base import EmbeddingError, EmbeddingProvider

logger = logging.getLogger(__name__)


class OpenAIEmbeddingProvider(EmbeddingProvider):
    """OpenAI embedding provider using text-embedding-3 models."""

    def __init__(
        self,
        api_key: str,
        model: str = "text-embedding-3-small",
        dimensions: int = 1536,
    ) -> None:
        """Initialize OpenAI embedding provider.

        Args:
            api_key: OpenAI API key
            model: Model name (text-embedding-3-small or text-embedding-3-large)
            dimensions: Embedding dimensions (default 1536 for small, 3072 for large)
        """
        self._client = AsyncOpenAI(api_key=api_key)
        self._model = model
        self._dimensions = dimensions

    async def generate_embedding(self, text: str, tenant_id: UUID) -> list[float]:
        """Generate embedding using OpenAI API.

        Args:
            text: The text to embed
            tenant_id: The tenant ID for tracking

        Returns:
            Embedding vector

        Raises:
            EmbeddingError: If embedding generation fails
        """
        try:
            response = await self._client.embeddings.create(
                model=self._model,
                input=text,
                dimensions=self._dimensions,
            )

            embedding = response.data[0].embedding
            logger.debug(
                "Generated embedding for tenant",
                extra={
                    "tenant_id": str(tenant_id),
                    "model": self._model,
                    "text_length": len(text),
                },
            )
            return embedding

        except Exception as e:
            logger.error(
                "Failed to generate embedding",
                extra={
                    "tenant_id": str(tenant_id),
                    "model": self._model,
                    "error": str(e),
                },
            )
            raise EmbeddingError(f"OpenAI embedding generation failed: {e}") from e

    async def generate_embeddings(
        self, texts: list[str], tenant_id: UUID
    ) -> list[list[float]]:
        """Generate embeddings for multiple texts.

        Args:
            texts: List of texts to embed
            tenant_id: The tenant ID for tracking

        Returns:
            List of embedding vectors

        Raises:
            EmbeddingError: If embedding generation fails
        """
        try:
            response = await self._client.embeddings.create(
                model=self._model,
                input=texts,
                dimensions=self._dimensions,
            )

            embeddings = [item.embedding for item in response.data]
            logger.debug(
                "Generated embeddings for tenant",
                extra={
                    "tenant_id": str(tenant_id),
                    "model": self._model,
                    "count": len(texts),
                },
            )
            return embeddings

        except Exception as e:
            logger.error(
                "Failed to generate embeddings",
                extra={
                    "tenant_id": str(tenant_id),
                    "model": self._model,
                    "error": str(e),
                },
            )
            raise EmbeddingError(f"OpenAI embeddings generation failed: {e}") from e

    @property
    def embedding_dimension(self) -> int:
        """Get the embedding dimension."""
        return self._dimensions

    @classmethod
    def from_settings(cls, settings: object) -> "OpenAIEmbeddingProvider":
        """Create provider from application settings.

        Args:
            settings: Application settings

        Returns:
            Configured OpenAI embedding provider
        """
        # Dynamic import to avoid circular dependency
        from app.settings import get_settings

        actual_settings = get_settings()
        return cls(
            api_key=actual_settings.openai_api_key,
            model="text-embedding-3-small",
            dimensions=1536,
        )
