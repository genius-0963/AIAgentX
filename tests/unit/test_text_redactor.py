"""Unit tests for text redactor."""

from __future__ import annotations

import pytest
from uuid import uuid4

from app.infrastructure.text.redactor import TextRedactor, RedactionResult
from app.infrastructure.text.classifier import ClassificationResult, SensitiveDataType
from app.domain.entities.memory import AllowedUseLabel


class TestTextRedactor:
    """Tests for TextRedactor."""

    @pytest.mark.asyncio
    async def test_redact_no_sensitive_data(self) -> None:
        redactor = TextRedactor()
        text = "Normal text without sensitive info."
        classification = ClassificationResult(
            has_sensitive_data=False,
            sensitive_types=[],
            allowed_use_label=AllowedUseLabel.PUBLIC,
            confidence=1.0,
        )
        tenant_id = uuid4()

        result = await redactor.redact(text, classification, tenant_id)

        assert isinstance(result, RedactionResult)
        assert result.redacted_text == text
        assert result.redaction_count == 0
        assert result.was_redacted is False

    @pytest.mark.asyncio
    async def test_redact_email(self) -> None:
        redactor = TextRedactor()
        text = "Contact user@example.com for info."
        classification = ClassificationResult(
            has_sensitive_data=True,
            sensitive_types=[SensitiveDataType.EMAIL],
            allowed_use_label=AllowedUseLabel.CONFIDENTIAL,
            confidence=0.8,
        )
        tenant_id = uuid4()

        result = await redactor.redact(text, classification, tenant_id)

        assert result.was_redacted is True
        assert result.redaction_count == 1
        assert "[REDACTED]" in result.redacted_text
        assert "user@example.com" not in result.redacted_text

    @pytest.mark.asyncio
    async def test_redact_multiple_emails(self) -> None:
        redactor = TextRedactor()
        text = "Email a@test.com and b@test.com"
        classification = ClassificationResult(
            has_sensitive_data=True,
            sensitive_types=[SensitiveDataType.EMAIL],
            allowed_use_label=AllowedUseLabel.CONFIDENTIAL,
            confidence=0.8,
        )
        tenant_id = uuid4()

        result = await redactor.redact(text, classification, tenant_id)

        assert result.redaction_count == 2
        assert result.redacted_text.count("[REDACTED]") == 2

    @pytest.mark.asyncio
    async def test_redact_phone(self) -> None:
        redactor = TextRedactor()
        text = "Call 555-123-4567 or 555.987.6543"
        classification = ClassificationResult(
            has_sensitive_data=True,
            sensitive_types=[SensitiveDataType.PHONE],
            allowed_use_label=AllowedUseLabel.CONFIDENTIAL,
            confidence=0.8,
        )
        tenant_id = uuid4()

        result = await redactor.redact(text, classification, tenant_id)

        assert result.redaction_count == 2
        assert "555-123-4567" not in result.redacted_text
        assert "555.987.6543" not in result.redacted_text

    @pytest.mark.asyncio
    async def test_redact_ssn(self) -> None:
        redactor = TextRedactor()
        text = "SSN: 123-45-6789"
        classification = ClassificationResult(
            has_sensitive_data=True,
            sensitive_types=[SensitiveDataType.SSN],
            allowed_use_label=AllowedUseLabel.RESTRICTED,
            confidence=0.8,
        )
        tenant_id = uuid4()

        result = await redactor.redact(text, classification, tenant_id)

        assert result.redaction_count == 1
        assert "123-45-6789" not in result.redacted_text

    @pytest.mark.asyncio
    async def test_redact_credit_card(self) -> None:
        redactor = TextRedactor()
        text = "Card: 1234-5678-9012-3456"
        classification = ClassificationResult(
            has_sensitive_data=True,
            sensitive_types=[SensitiveDataType.CREDIT_CARD],
            allowed_use_label=AllowedUseLabel.RESTRICTED,
            confidence=0.8,
        )
        tenant_id = uuid4()

        result = await redactor.redact(text, classification, tenant_id)

        assert result.redaction_count >= 1
        assert "1234-5678-9012-3456" not in result.redacted_text

    @pytest.mark.asyncio
    async def test_redact_api_key(self) -> None:
        redactor = TextRedactor()
        text = "api_key = 'sk-1234567890abcdef'"
        classification = ClassificationResult(
            has_sensitive_data=True,
            sensitive_types=[SensitiveDataType.API_KEY],
            allowed_use_label=AllowedUseLabel.RESTRICTED,
            confidence=0.8,
        )
        tenant_id = uuid4()

        result = await redactor.redact(text, classification, tenant_id)

        assert result.redaction_count >= 1
        assert "sk-1234567890abcdef" not in result.redacted_text

    @pytest.mark.asyncio
    async def test_redact_multiple_types(self) -> None:
        redactor = TextRedactor()
        text = "Email: user@test.com, Phone: 555-123-4567"
        classification = ClassificationResult(
            has_sensitive_data=True,
            sensitive_types=[SensitiveDataType.EMAIL, SensitiveDataType.PHONE],
            allowed_use_label=AllowedUseLabel.CONFIDENTIAL,
            confidence=0.8,
        )
        tenant_id = uuid4()

        result = await redactor.redact(text, classification, tenant_id)

        assert result.redaction_count == 2
        assert "user@test.com" not in result.redacted_text
        assert "555-123-4567" not in result.redacted_text

    @pytest.mark.asyncio
    async def test_redact_based_on_policy_public(self) -> None:
        redactor = TextRedactor()
        text = "user@example.com"
        tenant_id = uuid4()

        result = await redactor.redact_based_on_policy(text, AllowedUseLabel.PUBLIC, tenant_id)

        # PUBLIC content should not be redacted
        assert result.was_redacted is False
        assert result.redacted_text == text

    @pytest.mark.asyncio
    async def test_redact_based_on_policy_confidential(self) -> None:
        redactor = TextRedactor()
        text = "user@example.com"
        tenant_id = uuid4()

        result = await redactor.redact_based_on_policy(text, AllowedUseLabel.CONFIDENTIAL, tenant_id)

        # CONFIDENTIAL should trigger classification and redaction
        assert result.was_redacted is True
        assert "user@example.com" not in result.redacted_text