"""
TradeFlow AI — OpenTelemetry & Prometheus Observability Initialization
"""

import structlog
from fastapi import FastAPI
try:
    from opentelemetry import metrics, trace
    from opentelemetry.instrumentation.celery import CeleryInstrumentor
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
    from opentelemetry.instrumentation.redis import RedisInstrumentor
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.metrics.export import ConsoleMetricExporter, PeriodicExportingMetricReader
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
    OPENTELEMETRY_AVAILABLE = True
except Exception:  # pragma: no cover - optional observability
    OPENTELEMETRY_AVAILABLE = False

from ..config import settings

log = structlog.get_logger()

def setup_telemetry(app: FastAPI) -> None:
    """Initialize OpenTelemetry tracing and Prometheus metrics."""
    enabled = settings.OTEL_ENABLED
    if not enabled or not OPENTELEMETRY_AVAILABLE:
        log.info("OpenTelemetry is disabled or not installed. Skipping telemetry setup.")
        return

    # Setup Tracing
    resource = Resource.create({"service.name": "tradeflow-api", "service.version": "1.0.0"})
    tracer_provider = TracerProvider(resource=resource)

    # In production, use OTLPSpanExporter to send to Jaeger/Tempo
    # For now, we export to console for debug, but only if trace level is high
    exporter = ConsoleSpanExporter()
    span_processor = BatchSpanProcessor(exporter)
    tracer_provider.add_span_processor(span_processor)
    trace.set_tracer_provider(tracer_provider)

    # Setup Metrics
    metric_reader = PeriodicExportingMetricReader(ConsoleMetricExporter())
    meter_provider = MeterProvider(resource=resource, metric_readers=[metric_reader])
    metrics.set_meter_provider(meter_provider)

    # Instrument libraries
    FastAPIInstrumentor.instrument_app(app)
    CeleryInstrumentor().instrument()
    HTTPXClientInstrumentor().instrument()
    RedisInstrumentor().instrument()

    log.info("OpenTelemetry & Prometheus instrumentation initialized.")
