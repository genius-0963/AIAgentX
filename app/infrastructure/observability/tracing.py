"""OpenTelemetry tracing configuration and utilities."""

from __future__ import annotations

import logging
from collections.abc import Generator
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any

from opentelemetry import trace
from opentelemetry.baggage.propagation import W3CBaggagePropagator
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.propagate import set_global_textmap
from opentelemetry.propagators.composite import CompositePropagator
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.trace.sampling import Sampler
from opentelemetry.trace import SpanKind
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

if TYPE_CHECKING:
    from fastapi import FastAPI

    from app.settings import Settings

logger = logging.getLogger(__name__)


def configure_tracing(settings: Settings) -> TracerProvider | None:
    """Configure OpenTelemetry tracing with OTLP exporter.

    Args:
        settings: Application settings with OpenTelemetry configuration.

    Returns:
        Configured TracerProvider or None if tracing is disabled.
    """
    if not settings.otel_enabled:
        logger.info("OpenTelemetry tracing is disabled")
        return None

    # Create resource with service information
    resource = Resource.create(
        {
            "service.name": settings.otel_service_name,
            "service.version": "0.1.0",
            "deployment.environment": settings.environment.value,
        }
    )

    # Configure trace sampling
    sampler = _create_sampler(settings)

    # Create tracer provider with sampler
    tracer_provider = TracerProvider(resource=resource, sampler=sampler)
    trace.set_tracer_provider(tracer_provider)

    # Configure OTLP exporter
    otlp_exporter = OTLPSpanExporter(
        endpoint=settings.otel_exporter_otlp_endpoint,
        insecure=settings.otel_exporter_otlp_insecure,
    )

    # Add batch span processor
    tracer_provider.add_span_processor(BatchSpanProcessor(otlp_exporter))

    # Configure propagators for trace context propagation
    from opentelemetry.propagators.textmap import TextMapPropagator

    propagators: list[TextMapPropagator] = []
    for propagator_name in settings.otel_propagators.split(","):
        propagator_name = propagator_name.strip().lower()
        if propagator_name == "tracecontext":
            propagators.append(TraceContextTextMapPropagator())
        elif propagator_name == "baggage":
            propagators.append(W3CBaggagePropagator())

    if propagators:
        set_global_textmap(CompositePropagator(propagators))
        logger.info("Configured propagators: %s", settings.otel_propagators)

    # Auto-instrument libraries
    _setup_auto_instrumentation(settings)

    logger.info(
        "OpenTelemetry tracing configured",
        extra={
            "service_name": settings.otel_service_name,
            "exporter_endpoint": settings.otel_exporter_otlp_endpoint,
            "sampler": settings.otel_traces_sampler,
            "sampler_arg": settings.otel_traces_sampler_arg,
        },
    )

    return tracer_provider


def _create_sampler(settings: Settings) -> Sampler:
    """Create a sampler based on settings."""
    from opentelemetry.sdk.trace.sampling import (
        ALWAYS_OFF,
        ALWAYS_ON,
        ParentBasedTraceIdRatio,
    )

    sampler_name = settings.otel_traces_sampler.lower()
    sampler_arg = settings.otel_traces_sampler_arg

    if sampler_name == "parentbased_traceidratio":
        logger.info("Configured ParentBasedTraceIdRatio sampler with ratio: %s", sampler_arg)
        return ParentBasedTraceIdRatio(sampler_arg)
    if sampler_name == "always_on":
        logger.info("Configured ALWAYS_ON sampler")
        return ALWAYS_ON
    if sampler_name == "always_off":
        logger.info("Configured ALWAYS_OFF sampler")
        return ALWAYS_OFF

    logger.warning("Unknown sampler: %s, using default", sampler_name)
    return ParentBasedTraceIdRatio(0.1)  # Default sampler


def _setup_auto_instrumentation(settings: Settings) -> None:
    """Set up automatic instrumentation for supported libraries."""
    try:
        FastAPIInstrumentor().instrument()
        logger.info("FastAPI instrumentation enabled")
    except Exception as e:  # noqa: BLE001
        logger.warning("Failed to instrument FastAPI: %s", e)

    try:
        SQLAlchemyInstrumentor().instrument(enable_commenter=True, commenter_options={})
        logger.info("SQLAlchemy instrumentation enabled")
    except Exception as e:  # noqa: BLE001
        logger.warning("Failed to instrument SQLAlchemy: %s", e)

    try:
        RedisInstrumentor().instrument()
        logger.info("Redis instrumentation enabled")
    except Exception as e:  # noqa: BLE001
        logger.warning("Failed to instrument Redis: %s", e)

    try:
        HTTPXClientInstrumentor().instrument()
        logger.info("HTTPX instrumentation enabled")
    except Exception as e:  # noqa: BLE001
        logger.warning("Failed to instrument HTTPX: %s", e)


def instrument_fastapi_app(app: FastAPI, settings: Settings) -> None:
    """Instrument a FastAPI application with OpenTelemetry.

    Args:
        app: FastAPI application instance.
        settings: Application settings.
    """
    if not settings.otel_enabled:
        return

    try:
        FastAPIInstrumentor.instrument_app(
            app,
            tracer_provider=trace.get_tracer_provider(),
            excluded_urls="/healthz,/readyz,/metrics",
        )
        logger.info("FastAPI app instrumented with OpenTelemetry")
    except Exception as e:  # noqa: BLE001
        logger.warning("Failed to instrument FastAPI app: %s", e)


def get_tracer(name: str) -> trace.Tracer:
    """Get a tracer instance for the given name.

    Args:
        name: Name of the tracer (typically __name__).

    Returns:
        Tracer instance.
    """
    return trace.get_tracer(name)



@contextmanager
def start_span(
    name: str,
    kind: SpanKind = SpanKind.INTERNAL,
    attributes: dict[str, Any] | None = None,
    tracer_name: str | None = None,
) -> Generator[trace.Span, None, None]:
    """Context manager to start a new span.

    Args:
        name: Name of the span.
        kind: Span kind (default: INTERNAL).
        attributes: Optional attributes to set on the span.
        tracer_name: Optional tracer name (defaults to calling module).

    Yields:
        The created span.
    """
    tracer = get_tracer(tracer_name or "app")
    with tracer.start_as_current_span(name, kind=kind) as span:
        if attributes:
            for key, value in attributes.items():
                span.set_attribute(key, value)
        yield span


def add_span_attributes(attributes: dict[str, Any]) -> None:
    """Add attributes to the current span.

    Args:
        attributes: Dictionary of attributes to add.
    """
    span = trace.get_current_span()
    if span and span.is_recording():
        for key, value in attributes.items():
            span.set_attribute(key, value)


def set_span_status(status_code: trace.StatusCode, description: str | None = None) -> None:
    """Set the status of the current span.

    Args:
        status_code: Status code (OK, ERROR, UNSET).
        description: Optional description for the status.
    """
    span = trace.get_current_span()
    if span and span.is_recording():
        span.set_status(trace.Status(status_code, description))


def record_exception(exception: Exception, attributes: dict[str, Any] | None = None) -> None:
    """Record an exception in the current span.

    Args:
        exception: Exception to record.
        attributes: Optional additional attributes.
    """
    span = trace.get_current_span()
    if span and span.is_recording():
        span.record_exception(exception, attributes=attributes)
        span.set_status(trace.Status(trace.StatusCode.ERROR, str(exception)))


def get_trace_id() -> str | None:
    """Get the current trace ID as a hex string.

    Returns:
        Trace ID as hex string or None if no active span.
    """
    span = trace.get_current_span()
    if span and span.is_recording():
        return format(span.get_span_context().trace_id, "032x")
    return None


def get_span_id() -> str | None:
    """Get the current span ID as a hex string.

    Returns:
        Span ID as hex string or None if no active span.
    """
    span = trace.get_current_span()
    if span and span.is_recording():
        return format(span.get_span_context().span_id, "016x")
    return None