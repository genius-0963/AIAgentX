"""Unit tests for sensitive data classifier."""

from __future__ import annotations

import pytest
from uuid import uuid4

from app.infrastructure.text.classifier import (
    ClassificationResult,
    SensitiveDataClassifier,
    SensitiveDataType,
)
from app.domain.entities.memory import AllowedUseLabel


class TestSensitiveDataClassifier:
    """Tests for SensitiveDataClassifier."""

    def test_classify_no_sensitive_data(self) -> None:
        classifier = SensitiveDataClassifier()
        text = "This is a normal message without sensitive info."
        tenant_id = uuid4()

        result = classifier.classify(text, tenant_id)

        assert isinstance(result, ClassificationResult)
        assert result.has_sensitive_data is False
        assert result.sensitive_types == []
        assert result.allowed_use_label == AllowedUseLabel.PUBLIC
        assert result.confidence == 1.0

    def test_classify_email(self) -> None:
        classifier = SensitiveDataClassifier()
        text = "Contact me at user@example.com for more info."
        tenant_id = uuid4()

        result = classifier.classify(text, tenant_id)

        assert result.has_sensitive_data is True
        assert SensitiveDataType.EMAIL in result.sensitive_types
        assert result.allowed_use_label == AllowedUseLabel.CONFIDENTIAL

    def test_classify_phone(self) -> None:
        classifier = SensitiveDataClassifier()
        text = "Call me at 555-123-4567."
        tenant_id = uuid4()

        result = classifier.classify(text, tenant_id)

        assert result.has_sensitive_data is True
        assert SensitiveDataType.PHONE in result.sensitive_types
        assert result.allowed_use_label == AllowedUseLabel.CONFIDENTIAL

    def test_classify_ssn(self) -> None:
        classifier = SensitiveDataClassifier()
        text = "My SSN is 123-45-6789."
        tenant_id = uuid4()

        result = classifier.classify(text, tenant_id)

        assert result.has_sensitive_data is True
        assert SensitiveDataType.SSN in result.sensitive_types
        assert result.allowed_use_label == AllowedUseLabel.RESTRICTED

    def test_classify_credit_card(self) -> None:
        classifier = SensitiveDataClassifier()
        text = "Card: 1234 5678 9012 3456"
        tenant_id = uuid4()

        result = classifier.classify(text, tenant_id)

        assert result.has_sensitive_data is True
        assert SensitiveDataType.CREDIT_CARD in result.sensitive_types
        assert result.allowed_use_label == AllowedUseLabel.RESTRICTED

    def test_classify_api_key(self) -> None:
        classifier = SensitiveDataClassifier()
        text = "api_key = 'sk-1234567890abcdef'"
        tenant_id = uuid4()

        result = classifier.classify(text, tenant_id)

        assert result.has_sensitive_data is True
        assert SensitiveDataType.API_KEY in result.sensitive_types
        assert result.allowed_use_label == AllowedUseLabel.RESTRICTED

    def test_classify_password(self) -> None:
        classifier = SensitiveDataClassifier()
        text = "password: mysecret123"
        tenant_id = uuid4()

        result = classifier.classify(text, tenant_id)

        assert result.has_sensitive_data is True
        assert SensitiveDataType.PASSWORD in result.sensitive_types
        assert result.allowed_use_label == AllowedUseLabel.RESTRICTED

    def test_classify_ip_address(self) -> None:
        classifier = SensitiveDataClassifier()
        text = "Server IP: 192.168.1.1"
        tenant_id = uuid4()

        result = classifier.classify(text, tenant_id)

        assert result.has_sensitive_data is True
        assert SensitiveDataType.IP_ADDRESS in result.sensitive_types
        assert result.allowed_use_label == AllowedUseLabel.INTERNAL

    def test_classify_multiple_types(self) -> None:
        classifier = SensitiveDataClassifier()
        text = "Email: user@test.com, Phone: 555-123-4567, SSN: 123-45-6789"
        tenant_id = uuid4()

        result = classifier.classify(text, tenant_id)

        assert result.has_sensitive_data is True
        assert SensitiveDataType.EMAIL in result.sensitive_types
        assert SensitiveDataType.PHONE in result.sensitive_types
        assert SensitiveDataType.SSN in result.sensitive_types
        # Should be RESTRICTED due to SSN
        assert result.allowed_use_label == AllowedUseLabel.RESTRICTED

    def test_determine_allowed_use_restricted(self) -> None:
        classifier = SensitiveDataClassifier()
        types = [SensitiveDataType.SSN, SensitiveDataType.CREDIT_CARD]
        label = classifier._determine_allowed_use(types)
        assert label == AllowedUseLabel.RESTRICTED

    def test_determine_allowed_use_confidential(self) -> None:
        classifier = SensitiveDataClassifier()
        types = [SensitiveDataType.EMAIL, SensitiveDataType.PHONE]
        label = classifier._determine_allowed_use(types)
        assert label == AllowedUseLabel.CONFIDENTIAL

    def test_determine_allowed_use_internal(self) -> None:
        classifier = SensitiveDataClassifier()
        types = [SensitiveDataType.IP_ADDRESS]
        label = classifier._determine_allowed_use(types)
        assert label == AllowedUseLabel.INTERNAL

    def test_case_insensitive_detection(self) -> None:
        classifier = SensitiveDataClassifier()
        text = "API_KEY = 'secret123'"  # Uppercase
        tenant_id = uuid4()

        result = classifier.classify(text, tenant_id)

        assert result.has_sensitive_data is True
        assert SensitiveDataType.API_KEY in result.sensitive_types