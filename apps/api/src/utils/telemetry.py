"""
TradeFlow AI — OpenTelemetry & Prometheus Observability Initialization
"""

from opentelemetry import trace, metrics
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader, ConsoleMetricExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.celery import CeleryInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor

import structlog
from prometheus_client import make_asgi_app
from fastapi import FastAPI
import os

log = structlog.get_logger()

def setup_telemetry(app: FastAPI) -> None:
    """Initialize OpenTelemetry tracing and Prometheus metrics."""
    
    enabled = os.getenv("OTEL_ENABLED", "false").lower() == "true"
    if not enabled:
        log.info("OpenTelemetry is disabled. Set OTEL_ENABLED=true to enable.")
        # We still mount prometheus for basic metrics
        metrics_app = make_asgi_app()
        app.mount("/metrics", metrics_app)
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

    # Mount Prometheus
    metrics_app = make_asgi_app()
    app.mount("/metrics", metrics_app)

    log.info("OpenTelemetry & Prometheus instrumentation initialized.")
