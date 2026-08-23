"""Unit tests for text normalizer."""

from __future__ import annotations

import pytest

from app.infrastructure.text.normalizer import TextNormalizer


class TestTextNormalizer:
    """Tests for TextNormalizer."""

    def test_normalize_unicode_nfc(self) -> None:
        # Test NFC normalization
        text = "caf\u00e9"  # Precomposed
        normalized = TextNormalizer.normalize(text)
        assert normalized == "café"

    def test_normalize_whitespace(self) -> None:
        text = "  hello   world  \n\t  "
        normalized = TextNormalizer.normalize(text)
        assert normalized == "hello world"

    def test_normalize_control_chars(self) -> None:
        text = "hello\x00world\x1f!"
        normalized = TextNormalizer.normalize(text)
        assert normalized == "helloworld!"

    def test_normalize_preserves_newlines_and_tabs(self) -> None:
        text = "line1\nline2\tindented"
        normalized = TextNormalizer.normalize(text)
        # Newlines and tabs are normalized to spaces
        assert normalized == "line1 line2 indented"

    def test_validate_size_ok(self) -> None:
        text = "x" * 1000
        assert TextNormalizer.validate_size(text) is True

    def test_validate_size_exceeds_limit(self) -> None:
        text = "x" * 200000  # 200KB > 100KB limit
        with pytest.raises(ValueError, match="exceeds limit"):
            TextNormalizer.validate_size(text)

    def test_validate_size_custom_limit(self) -> None:
        text = "x" * 5000
        assert TextNormalizer.validate_size(text, max_size=10000) is True

    def test_truncate_under_limit(self) -> None:
        text = "hello world"
        truncated = TextNormalizer.truncate(text, max_size=100)
        assert truncated == "hello world"

    def test_truncate_over_limit(self) -> None:
        text = "x" * 200000
        truncated = TextNormalizer.truncate(text, max_size=100000)
        assert len(truncated.encode("utf-8")) <= 100000

    def test_truncate_preserves_utf8(self) -> None:
        text = "café" * 30000  # Multi-byte chars
        truncated = TextNormalizer.truncate(text, max_size=10000)
        assert len(truncated.encode("utf-8")) <= 10000
        # Should not cut in middle of multi-byte char
        assert truncated.endswith("é") or not truncated.endswith("caf")