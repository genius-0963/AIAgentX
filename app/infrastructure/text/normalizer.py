"""Text normalization utilities."""

from __future__ import annotations

import re
import unicodedata


class TextNormalizer:
    """Normalizes text for memory storage."""

    MAX_MEMORY_SIZE = 100_000  # 100KB limit per memory record

    @staticmethod
    def normalize(text: str) -> str:
        """Normalize text for storage.

        Args:
            text: The text to normalize

        Returns:
            Normalized text

        Raises:
            ValueError: If text exceeds size limit
        """
        # Normalize Unicode to NFC form
        normalized = unicodedata.normalize("NFC", text)

        # Normalize whitespace
        normalized = re.sub(r"\s+", " ", normalized).strip()

        # Remove control characters except common ones
        normalized = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", normalized)

        return normalized

    @staticmethod
    def validate_size(text: str, max_size: int | None = None) -> bool:
        """Validate text size against limit.

        Args:
            text: The text to validate
            max_size: Maximum size in bytes (defaults to class constant)

        Returns:
            True if size is acceptable

        Raises:
            ValueError: If text exceeds size limit
        """
        limit = max_size or TextNormalizer.MAX_MEMORY_SIZE
        size = len(text.encode("utf-8"))

        if size > limit:
            raise ValueError(f"Text size {size} bytes exceeds limit {limit} bytes")

        return True

    @staticmethod
    def truncate(text: str, max_size: int | None = None) -> str:
        """Truncate text to fit within size limit.

        Args:
            text: The text to truncate
            max_size: Maximum size in bytes (defaults to class constant)

        Returns:
            Truncated text
        """
        limit = max_size or TextNormalizer.MAX_MEMORY_SIZE

        if len(text.encode("utf-8")) <= limit:
            return text

        # Binary search for truncation point
        low, high = 0, len(text)
        while low < high:
            mid = (low + high + 1) // 2
            if len(text[:mid].encode("utf-8")) <= limit:
                low = mid
            else:
                high = mid - 1

        return text[:low]
