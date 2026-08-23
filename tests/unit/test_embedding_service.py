"""Unit tests for embedding service."""

from __future__ import annotations

import pytest
from uuid import uuid4

from app.infrastructure.embeddings.base import EmbeddingService
from app.infrastructure.embeddings.fake import FakeEmbeddingProvider
from app.infrastructure.embeddings.openai import OpenAIEmbeddingProvider


class TestFakeEmbeddingProvider:
    """Tests for FakeEmbeddingProvider."""

    def test_init_default_dimensions(self) -> None:
        provider = FakeEmbeddingProvider()
        assert provider.embedding_dimension == 1536

    def test_init_custom_dimensions(self) -> None:
        provider = FakeEmbeddingProvider(dimensions=768)
        assert provider.embedding_dimension == 768

    @pytest.mark.asyncio
    async def test_generate_embedding_deterministic(self) -> None:
        provider = FakeEmbeddingProvider(dimensions=10)
        tenant_id = uuid4()
        text = "test text"

        emb1 = await provider.generate_embedding(text, tenant_id)
        emb2 = await provider.generate_embedding(text, tenant_id)

        assert emb1 == emb2
        assert len(emb1) == 10

    @pytest.mark.asyncio
    async def test_generate_embedding_different_texts(self) -> None:
        provider = FakeEmbeddingProvider(dimensions=10)
        tenant_id = uuid4()

        emb1 = await provider.generate_embedding("text one", tenant_id)
        emb2 = await provider.generate_embedding("text two", tenant_id)

        assert emb1 != emb2
        assert len(emb1) == 10
        assert len(emb2) == 10

    @pytest.mark.asyncio
    async def test_generate_embedding_different_tenants(self) -> None:
        provider = FakeEmbeddingProvider(dimensions=10)
        text = "same text"

        emb1 = await provider.generate_embedding(text, uuid4())
        emb2 = await provider.generate_embedding(text, uuid4())

        # Different tenants should produce different embeddings
        assert emb1 != emb2

    @pytest.mark.asyncio
    async def test_generate_embeddings_batch(self) -> None:
        provider = FakeEmbeddingProvider(dimensions=5)
        tenant_id = uuid4()
        texts = ["text one", "text two", "text three"]

        embeddings = await provider.generate_embeddings(texts, tenant_id)

        assert len(embeddings) == 3
        for emb in embeddings:
            assert len(emb) == 5

    @pytest.mark.asyncio
    async def test_embedding_values_in_range(self) -> None:
        provider = FakeEmbeddingProvider(dimensions=100)
        tenant_id = uuid4()

        embedding = await provider.generate_embedding("test", tenant_id)

        # Values should be in [-1, 1] range
        for val in embedding:
            assert -1.0 <= val <= 1.0


class TestEmbeddingService:
    """Tests for EmbeddingService with fallback."""

    @pytest.mark.asyncio
    async def test_primary_provider_success(self) -> None:
        primary = FakeEmbeddingProvider(dimensions=10)
        fallback = FakeEmbeddingProvider(dimensions=10)
        service = EmbeddingService(primary_provider=primary, fallback_provider=fallback)

        embedding = await service.generate_embedding("test", uuid4())

        assert len(embedding) == 10

    @pytest.mark.asyncio
    async def test_fallback_on_primary_failure(self) -> None:
        class FailingProvider(FakeEmbeddingProvider):
            async def generate_embedding(self, text: str, tenant_id: uuid4) -> list[float]:
                raise Exception("Primary failed")

        primary = FailingProvider(dimensions=10)
        fallback = FakeEmbeddingProvider(dimensions=10)
        service = EmbeddingService(primary_provider=primary, fallback_provider=fallback)

        embedding = await service.generate_embedding("test", uuid4())

        assert len(embedding) == 10

    @pytest.mark.asyncio
    async def test_both_fail_raises(self) -> None:
        class FailingProvider(FakeEmbeddingProvider):
            async def generate_embedding(self, text: str, tenant_id: uuid4) -> list[float]:
                raise Exception("Failed")

        primary = FailingProvider(dimensions=10)
        fallback = FailingProvider(dimensions=10)
        service = EmbeddingService(primary_provider=primary, fallback_provider=fallback)

        with pytest.raises(Exception, match="Failed to generate embedding"):
            await service.generate_embedding("test", uuid4())

    @pytest.mark.asyncio
    async def test_no_fallback_raises(self) -> None:
        class FailingProvider(FakeEmbeddingProvider):
            async def generate_embedding(self, text: str, tenant_id: uuid4) -> list[float]:
                raise Exception("Primary failed")

        primary = FailingProvider(dimensions=10)
        service = EmbeddingService(primary_provider=primary, fallback_provider=None)

        with pytest.raises(Exception, match="Failed to generate embedding"):
            await service.generate_embedding("test", uuid4())

    def test_embedding_dimension_property(self) -> None:
        primary = FakeEmbeddingProvider(dimensions=768)
        service = EmbeddingService(primary_provider=primary)

        assert service.embedding_dimension == 768