"""Unit tests for text chunker."""

from __future__ import annotations

import pytest

from app.infrastructure.text.chunker import TextChunker


class TestTextChunker:
    """Tests for TextChunker."""

    def test_init_defaults(self) -> None:
        chunker = TextChunker()
        assert chunker._chunk_size == 600
        assert chunker._overlap == 0.1

    def test_init_custom_params(self) -> None:
        chunker = TextChunker(chunk_size=500, overlap=0.2)
        assert chunker._chunk_size == 500
        assert chunker._overlap == 0.2

    def test_init_invalid_chunk_size(self) -> None:
        with pytest.raises(ValueError, match="chunk_size must be between"):
            TextChunker(chunk_size=50)

        with pytest.raises(ValueError, match="chunk_size must be between"):
            TextChunker(chunk_size=2000)

    def test_init_invalid_overlap(self) -> None:
        with pytest.raises(ValueError, match="overlap must be between"):
            TextChunker(overlap=-0.1)

        with pytest.raises(ValueError, match="overlap must be between"):
            TextChunker(overlap=1.0)

    def test_chunk_empty_text(self) -> None:
        chunker = TextChunker()
        chunks = chunker.chunk_text("")
        assert chunks == []

    def test_chunk_short_text(self) -> None:
        chunker = TextChunker(chunk_size=100, overlap=0.0)
        text = "This is a short text."
        chunks = chunker.chunk_text(text)
        assert len(chunks) == 1
        assert chunks[0] == text

    def test_chunk_long_text_fallback(self) -> None:
        # Use chunker without tiktoken (fallback mode)
        chunker = TextChunker(chunk_size=50, overlap=0.1)
        text = " ".join([f"word{i}" for i in range(100)])  # ~600 chars
        chunks = chunker.chunk_text(text)

        assert len(chunks) > 1
        # Check overlap
        for i in range(1, len(chunks)):
            # Some overlap should exist
            assert len(chunks[i]) > 0

    def test_chunk_preserves_content(self) -> None:
        chunker = TextChunker(chunk_size=100, overlap=0.0)
        text = "First sentence. Second sentence. Third sentence. Fourth sentence."
        chunks = chunker.chunk_text(text)
        # Join chunks should contain all original words
        joined = " ".join(chunks)
        assert "First" in joined
        assert "Fourth" in joined

    def test_count_tokens_fallback(self) -> None:
        chunker = TextChunker()
        text = "This is a test sentence with ten words here."
        tokens = chunker.count_tokens(text)
        # Fallback: 4 chars per token
        expected = len(text) // 4
        assert tokens == expected