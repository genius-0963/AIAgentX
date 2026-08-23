"""Text redaction utilities for sensitive data protection."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING
from uuid import UUID

from app.domain.entities.memory import AllowedUseLabel
from app.infrastructure.text.classifier import ClassificationResult, SensitiveDataClassifier, SensitiveDataType

if TYPE_CHECKING:
    try:
        from presidio_anonymizer import AnonymizerEngine
    except ImportError:
        AnonymizerEngine = None


@dataclass
class RedactionResult:
    """Result of text redaction."""

    redacted_text: str
    redaction_count: int
    was_redacted: bool


class TextRedactor:
    """Redacts sensitive data from text based on policy."""

    def __init__(self, use_presidio: bool = False) -> None:
        """Initialize text redactor.

        Args:
            use_presidio: Whether to use Presidio for advanced redaction
        """
        self._use_presidio = use_presidio
        self._presidio_anonymizer = None
        self._classifier = SensitiveDataClassifier(use_presidio=use_presidio)

        if use_presidio and AnonymizerEngine is not None:
            try:
                self._presidio_anonymizer = AnonymizerEngine()
            except Exception:
                pass

    async def redact(
        self,
        text: str,
        classification: ClassificationResult,
        tenant_id: UUID,
    ) -> RedactionResult:
        """Redact sensitive data from text based on classification.

        Args:
            text: The text to redact
            classification: Classification result from classifier
            tenant_id: The tenant ID for tenant-specific policies

        Returns:
            Redaction result
        """
        if not classification.has_sensitive_data:
            return RedactionResult(
                redacted_text=text,
                redaction_count=0,
                was_redacted=False,
            )

        # Use Presidio if available for more accurate redaction
        if self._presidio_anonymizer:
            return self._redact_with_presidio(text, classification)

        # Fallback to pattern-based redaction
        return self._redact_with_patterns(text, classification)

    def _redact_with_presidio(
        self,
        text: str,
        classification: ClassificationResult,
    ) -> RedactionResult:
        """Redact using Presidio anonymizer.

        Args:
            text: The text to redact
            classification: Classification result

        Returns:
            Redaction result
        """
        try:
            # Map our sensitive types to Presidio entity types
            type_mapping = {
                SensitiveDataType.EMAIL: "EMAIL",
                SensitiveDataType.PHONE: "PHONE_NUMBER",
                SensitiveDataType.SSN: "US_SSN",
                SensitiveDataType.CREDIT_CARD: "CREDIT_CARD",
                SensitiveDataType.IP_ADDRESS: "IP_ADDRESS",
            }

            # Configure anonymizer with custom operators
            anonymized_result = self._presidio_anonymizer.anonymize(
                text=text,
                operators=[{"type": "replace", "params": {"new_value": "[REDACTED]"}}],
            )

            # Count redactions (rough estimate based on pattern matches)
            redaction_count = len(classification.sensitive_types)

            return RedactionResult(
                redacted_text=anonymized_result.text,
                redaction_count=redaction_count,
                was_redacted=True,
            )

        except Exception:
            # Fallback to pattern-based if Presidio fails
            return self._redact_with_patterns(text, classification)

    def _redact_with_patterns(
        self,
        text: str,
        classification: ClassificationResult,
    ) -> RedactionResult:
        """Redact using pattern matching.

        Args:
            text: The text to redact
            classification: Classification result

        Returns:
            Redaction result
        """
        redacted_text = text
        redaction_count = 0

        # Redact each detected sensitive type
        for sensitive_type in classification.sensitive_types:
            pattern = SensitiveDataClassifier.PATTERNS.get(sensitive_type)
            if pattern:
                matches = re.findall(pattern, redacted_text, re.IGNORECASE)
                redaction_count += len(matches)
                redacted_text = re.sub(pattern, "[REDACTED]", redacted_text, flags=re.IGNORECASE)

        return RedactionResult(
            redacted_text=redacted_text,
            redaction_count=redaction_count,
            was_redacted=redaction_count > 0,
        )

    async def redact_based_on_policy(
        self,
        text: str,
        allowed_use_label: AllowedUseLabel,
        tenant_id: UUID,
    ) -> RedactionResult:
        """Redact text based on allowed use policy.

        Args:
            text: The text to redact
            allowed_use_label: The allowed use label for the content
            tenant_id: The tenant ID for tenant-specific policies

        Returns:
            Redaction result
        """
        # If content is public, no redaction needed
        if allowed_use_label == AllowedUseLabel.PUBLIC:
            return RedactionResult(
                redacted_text=text,
                redaction_count=0,
                was_redacted=False,
            )

        # Classify the text first
        classification = await self._classifier.classify(text, tenant_id)

        # If classification says no sensitive data, return as-is
        if not classification.has_sensitive_data:
            return RedactionResult(
                redacted_text=text,
                redaction_count=0,
                was_redacted=False,
            )

        # Redact based on policy
        return await self.redact(text, classification, tenant_id)
