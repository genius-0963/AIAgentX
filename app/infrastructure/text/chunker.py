"""Text chunking utilities for memory storage."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    try:
        import tiktoken
    except ImportError:
        tiktoken = None


class TextChunker:
    """Chunks text into smaller pieces for embedding generation."""

    DEFAULT_CHUNK_SIZE = 600  # tokens
    DEFAULT_OVERLAP = 0.1  # 10% overlap
    MIN_CHUNK_SIZE = 100  # tokens
    MAX_CHUNK_SIZE = 1000  # tokens

    def __init__(
        self,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        overlap: float = DEFAULT_OVERLAP,
        encoding_name: str = "cl100k_base",
    ) -> None:
        """Initialize text chunker.

        Args:
            chunk_size: Target chunk size in tokens
            overlap: Overlap ratio between chunks (0.0 to 1.0)
            encoding_name: Tiktoken encoding name
        """
        if not MIN_CHUNK_SIZE <= chunk_size <= MAX_CHUNK_SIZE:
            raise ValueError(f"chunk_size must be between {MIN_CHUNK_SIZE} and {MAX_CHUNK_SIZE}")

        if not 0.0 <= overlap < 1.0:
            raise ValueError("overlap must be between 0.0 and 1.0")

        self._chunk_size = chunk_size
        self._overlap = overlap
        self._encoding_name = encoding_name
        self._tokenizer = None

        # Try to initialize tiktoken
        if tiktoken is not None:
            try:
                self._tokenizer = tiktoken.get_encoding(encoding_name)
            except Exception:
                pass

    def chunk_text(self, text: str) -> list[str]:
        """Chunk text into smaller pieces.

        Args:
            text: The text to chunk

        Returns:
            List of text chunks
        """
        if not text:
            return []

        if self._tokenizer:
            return self._chunk_with_tokenizer(text)
        else:
            return self._chunk_fallback(text)

    def _chunk_with_tokenizer(self, text: str) -> list[str]:
        """Chunk text using tiktoken tokenizer.

        Args:
            text: The text to chunk

        Returns:
            List of text chunks
        """
        tokens = self._tokenizer.encode(text)
        chunk_size = self._chunk_size
        overlap_size = int(chunk_size * self._overlap)

        chunks = []
        start = 0

        while start < len(tokens):
            end = min(start + chunk_size, len(tokens))
            chunk_tokens = tokens[start:end]
            chunk_text = self._tokenizer.decode(chunk_tokens)
            chunks.append(chunk_text)

            start = end - overlap_size
            if start >= len(tokens):
                break

        return chunks

    def _chunk_fallback(self, text: str) -> list[str]:
        """Chunk text using character-based fallback.

        Args:
            text: The text to chunk

        Returns:
            List of text chunks
        """
        # Estimate 4 characters per token
        char_chunk_size = self._chunk_size * 4
        overlap_size = int(char_chunk_size * self._overlap)

        chunks = []
        start = 0

        while start < len(text):
            end = min(start + char_chunk_size, len(text))

            # Try to break at sentence boundary
            if end < len(text):
                # Look for sentence endings
                sentence_end = text.rfind(". ", start, end)
                if sentence_end > start + char_chunk_size // 2:
                    end = sentence_end + 2

            chunk_text = text[start:end].strip()
            if chunk_text:
                chunks.append(chunk_text)

            start = end - overlap_size
            if start >= len(text):
                break

        return chunks

    def count_tokens(self, text: str) -> int:
        """Count tokens in text.

        Args:
            text: The text to count tokens for

        Returns:
            Number of tokens
        """
        if self._tokenizer:
            return len(self._tokenizer.encode(text))
        else:
            # Fallback: estimate 4 characters per token
            return len(text) // 4
