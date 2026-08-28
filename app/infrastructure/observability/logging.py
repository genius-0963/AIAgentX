"""Structured JSON logging configured via :mod:`structlog`."""

from __future__ import annotations

import logging
import re
import sys
from typing import TYPE_CHECKING, Any

import structlog
from structlog.types import Processor

if TYPE_CHECKING:
    from app.settings import Settings

try:
    from opentelemetry import trace

    OTEL_AVAILABLE = True
except ImportError:
    OTEL_AVAILABLE = False


class SensitiveDataRedactor:
    """Processor to redact sensitive data from log entries."""

    def __init__(self, redact_keys: list[str]) -> None:
        self.redact_keys = redact_keys
        self._compile_patterns()

    def _compile_patterns(self) -> None:
        """Compile regex patterns for sensitive key matching."""
        self.patterns = [
            re.compile(rf"\b{re.escape(key)}\b", re.IGNORECASE) for key in self.redact_keys
        ]

    def __call__(
        self, logger: structlog.stdlib.BoundLogger, method_name: str, event_dict: dict[str, Any]
    ) -> dict[str, Any]:
        """Redact sensitive keys from the event dictionary."""
        redacted: dict[str, Any] = {}
        for key, value in event_dict.items():
            if self._is_sensitive_key(key):
                redacted[key] = "[REDACTED]"
            elif isinstance(value, dict):
                redacted[key] = self._redact_dict(value)
            elif isinstance(value, list):
                redacted[key] = [
                    self._redact_dict(item) if isinstance(item, dict) else item
                    for item in value
                ]
            else:
                redacted[key] = value
        return redacted

    def _is_sensitive_key(self, key: str) -> bool:
        """Check if a key matches any sensitive pattern."""
        return any(pattern.search(key) for pattern in self.patterns)

    def _redact_dict(self, data: dict[str, Any]) -> dict[str, Any]:
        """Recursively redact sensitive keys in a dictionary."""
        result: dict[str, Any] = {}
        for k, v in data.items():
            if isinstance(k, str) and self._is_sensitive_key(k):
                result[k] = "[REDACTED]"
            else:
                result[k] = v
        return result


class TraceContextInjector:
    """Processor to inject trace context (trace_id, span_id) into log entries."""

    def __call__(
        self, logger: structlog.stdlib.BoundLogger, method_name: str, event_dict: dict[str, Any]
    ) -> dict[str, Any]:
        """Inject trace context into the event dictionary."""
        if not OTEL_AVAILABLE:
            return event_dict

        span = trace.get_current_span()
        if span and span.is_recording():
            span_context = span.get_span_context()
            if span_context.trace_id != 0:
                event_dict["trace_id"] = format(span_context.trace_id, "032x")
            if span_context.span_id != 0:
                event_dict["span_id"] = format(span_context.span_id, "016x")
        return event_dict


class LogLevelOverrideFilter:
    """Filter to apply log level overrides based on logger name."""

    def __init__(self, overrides: dict[str, str]) -> None:
        self.overrides = overrides
        self._compile_overrides()

    def _compile_overrides(self) -> None:
        """Convert string levels to logging constants."""
        self.level_map = {}
        for logger_name, level_str in self.overrides.items():
            self.level_map[logger_name] = getattr(logging, level_str.upper(), logging.INFO)

    def filter(self, record: logging.LogRecord) -> bool:
        """Filter log records based on level overrides."""
        logger_name = record.name
        for override_name, override_level in self.level_map.items():
            if logger_name.startswith(override_name):
                return record.levelno >= override_level
        return True


def configure_logging(settings: Settings) -> None:
    """Configure structlog + stdlib logging for JSON output in non-dev envs."""
    level = getattr(logging, settings.log_level.upper(), logging.INFO)

    # Build shared processors
    shared_processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
    ]

    # Add sensitive data redaction if enabled
    redact_keys = settings.log_redact_keys_list
    if redact_keys:
        redact_processor = SensitiveDataRedactor(redact_keys)
        shared_processors.append(redact_processor)  # type: ignore[arg-type]

    # Add trace context injection if OpenTelemetry is available
    if OTEL_AVAILABLE:
        trace_injector = TraceContextInjector()
        shared_processors.append(trace_injector)  # type: ignore[arg-type]

    # Determine renderer based on log_format setting
    use_json = (
        settings.log_format == "json"
        or settings.is_production
        or settings.environment.value == "staging"
    )
    if use_json:
        renderer: Processor = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=True)

    shared_processors.append(renderer)

    structlog.configure(
        processors=shared_processors,
        wrapper_class=structlog.make_filtering_bound_logger(level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=True,
    )

    # Configure stdlib logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=level,
        force=True,
    )

    # Apply log level overrides
    level_overrides = settings.log_level_overrides_dict
    if level_overrides:
        level_filter = LogLevelOverrideFilter(level_overrides)
        logging.getLogger().addFilter(level_filter)

    logging.info(
        "Logging configured",
        extra={
            "log_format": settings.log_format,
            "log_level": settings.log_level,
            "redact_keys_count": len(settings.log_redact_keys_list),
            "level_overrides_count": len(settings.log_level_overrides_dict),
        },
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Return a configured logger."""
    return structlog.get_logger(name)  # type: ignore[no-any-return]