"""Fake embedding provider for testing."""

from __future__ import annotations

import hashlib
from uuid import UUID

from app.infrastructure.embeddings.base import EmbeddingProvider


class FakeEmbeddingProvider(EmbeddingProvider):
    """Fake embedding provider that generates deterministic embeddings for testing."""

    def __init__(self, dimensions: int = 1536) -> None:
        """Initialize fake embedding provider.

        Args:
            dimensions: Embedding dimensions (default 1536)
        """
        self._dimensions = dimensions

    async def generate_embedding(self, text: str, tenant_id: UUID) -> list[float]:
        """Generate deterministic embedding based on text hash.

        Args:
            text: The text to embed
            tenant_id: The tenant ID (included in hash for tenant isolation)

        Returns:
            Deterministic embedding vector
        """
        # Create a deterministic hash based on text and tenant
        hash_input = f"{tenant_id}:{text}"
        hash_bytes = hashlib.sha256(hash_input.encode()).digest()

        # Convert hash bytes to float values in range [-1, 1]
        embedding = []
        for i in range(self._dimensions):
            # Use cyclic access to hash bytes
            byte_idx = i % len(hash_bytes)
            # Convert byte to float in range [-1, 1]
            value = (hash_bytes[byte_idx] / 127.5) - 1.0
            embedding.append(value)

        return embedding

    async def generate_embeddings(
        self, texts: list[str], tenant_id: UUID
    ) -> list[list[float]]:
        """Generate embeddings for multiple texts.

        Args:
            texts: List of texts to embed
            tenant_id: The tenant ID

        Returns:
            List of deterministic embedding vectors
        """
        return [await self.generate_embedding(text, tenant_id) for text in texts]

    @property
    def embedding_dimension(self) -> int:
        """Get the embedding dimension."""
        return self._dimensions

    @classmethod
    def from_settings(cls, settings: object) -> "FakeEmbeddingProvider":
        """Create provider from application settings.

        Args:
            settings: Application settings

        Returns:
            Configured fake embedding provider
        """
        return cls(dimensions=1536)
