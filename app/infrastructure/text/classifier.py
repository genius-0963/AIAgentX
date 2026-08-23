"""Sensitive data classification utilities."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING
from uuid import UUID

from app.domain.entities.memory import AllowedUseLabel

if TYPE_CHECKING:
    try:
        from presidio_analyzer import AnalyzerEngine
    except ImportError:
        AnalyzerEngine = None


class SensitiveDataType(str, Enum):
    """Types of sensitive data."""

    EMAIL = "email"
    PHONE = "phone"
    SSN = "ssn"
    CREDIT_CARD = "credit_card"
    IP_ADDRESS = "ip_address"
    API_KEY = "api_key"
    PASSWORD = "password"
    PERSONAL_NAME = "personal_name"


@dataclass
class ClassificationResult:
    """Result of data classification."""

    has_sensitive_data: bool
    sensitive_types: list[SensitiveDataType]
    allowed_use_label: AllowedUseLabel
    confidence: float


class SensitiveDataClassifier:
    """Classifies sensitive data in text."""

    # Predefined patterns for common sensitive data
    PATTERNS = {
        SensitiveDataType.EMAIL: r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
        SensitiveDataType.PHONE: r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b",
        SensitiveDataType.SSN: r"\b\d{3}-\d{2}-\d{4}\b",
        SensitiveDataType.CREDIT_CARD: r"\b(?:\d[ -]*?){13,16}\b",
        SensitiveDataType.IP_ADDRESS: r"\b(?:\d{1,3}\.){3}\d{1,3}\b",
        SensitiveDataType.API_KEY: r"(?i)(api[_-]?key|apikey)\s*[:=]\s*['\"]?[a-zA-Z0-9_\-]+['\"]?",
        SensitiveDataType.PASSWORD: r"(?i)(password|passwd|pwd)\s*[:=]\s*['\"]?[^\s'\"]+['\"]?",
    }

    def __init__(self, use_presidio: bool = False) -> None:
        """Initialize sensitive data classifier.

        Args:
            use_presidio: Whether to use Presidio for advanced PII detection
        """
        self._use_presidio = use_presidio
        self._presidio_analyzer = None

        if use_presidio and AnalyzerEngine is not None:
            try:
                self._presidio_analyzer = AnalyzerEngine()
            except Exception:
                pass

    async def classify(self, text: str, tenant_id: UUID) -> ClassificationResult:
        """Classify sensitive data in text.

        Args:
            text: The text to classify
            tenant_id: The tenant ID for tenant-specific rules

        Returns:
            Classification result
        """
        sensitive_types = self._detect_sensitive_data(text)

        if not sensitive_types:
            return ClassificationResult(
                has_sensitive_data=False,
                sensitive_types=[],
                allowed_use_label=AllowedUseLabel.PUBLIC,
                confidence=1.0,
            )

        # Determine allowed use label based on sensitivity
        allowed_use_label = self._determine_allowed_use(sensitive_types)

        return ClassificationResult(
            has_sensitive_data=True,
            sensitive_types=sensitive_types,
            allowed_use_label=allowed_use_label,
            confidence=0.8,  # Moderate confidence for pattern-based detection
        )

    def _detect_sensitive_data(self, text: str) -> list[SensitiveDataType]:
        """Detect sensitive data using patterns.

        Args:
            text: The text to analyze

        Returns:
            List of detected sensitive data types
        """
        detected = []

        # Use Presidio if available
        if self._presidio_analyzer:
            try:
                results = self._presidio_analyzer.analyze(
                    text=text,
                    language="en",
                )
                # Map Presidio entity types to our types
                presidio_mapping = {
                    "EMAIL": SensitiveDataType.EMAIL,
                    "PHONE_NUMBER": SensitiveDataType.PHONE,
                    "US_SSN": SensitiveDataType.SSN,
                    "CREDIT_CARD": SensitiveDataType.CREDIT_CARD,
                    "IP_ADDRESS": SensitiveDataType.IP_ADDRESS,
                }
                for result in results:
                    if result.entity_type in presidio_mapping:
                        mapped_type = presidio_mapping[result.entity_type]
                        if mapped_type not in detected:
                            detected.append(mapped_type)
            except Exception:
                pass

        # Fallback to pattern matching
        for data_type, pattern in self.PATTERNS.items():
            if data_type not in detected and re.search(pattern, text, re.IGNORECASE):
                detected.append(data_type)

        return detected

    def _determine_allowed_use(self, sensitive_types: list[SensitiveDataType]) -> AllowedUseLabel:
        """Determine allowed use label based on sensitive data types.

        Args:
            sensitive_types: List of detected sensitive data types

        Returns:
            Appropriate allowed use label
        """
        # High sensitivity data
        high_sensitivity = {SensitiveDataType.SSN, SensitiveDataType.CREDIT_CARD, SensitiveDataType.API_KEY, SensitiveDataType.PASSWORD}
        if any(t in high_sensitivity for t in sensitive_types):
            return AllowedUseLabel.RESTRICTED

        # Medium sensitivity data
        medium_sensitivity = {SensitiveDataType.EMAIL, SensitiveDataType.PHONE}
        if any(t in medium_sensitivity for t in sensitive_types):
            return AllowedUseLabel.CONFIDENTIAL

        # Low sensitivity
        return AllowedUseLabel.INTERNAL
