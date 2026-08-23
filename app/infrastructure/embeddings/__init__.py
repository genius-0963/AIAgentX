"""Embedding service infrastructure layer."""

from __future__ import annotations

from app.infrastructure.embeddings.base import EmbeddingProvider, EmbeddingService
from app.infrastructure.embeddings.fake import FakeEmbeddingProvider
from app.infrastructure.embeddings.openai import OpenAIEmbeddingProvider

__all__ = [
    "EmbeddingProvider",
    "EmbeddingService",
    "OpenAIEmbeddingProvider",
    "FakeEmbeddingProvider",
]
