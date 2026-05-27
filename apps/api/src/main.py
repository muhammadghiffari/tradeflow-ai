"""
TradeFlow AI — FastAPI Application Entry Point

PRD §1.4 — Main application setup with lifespan management,
middleware, and router registration.
"""

from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

import sentry_sdk
import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from prometheus_fastapi_instrumentator import Instrumentator
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

from .config import settings
from .routers import batches, hs_recommend, blockchain, admin
from .dependencies import init_supabase, close_supabase
from .utils.telemetry import setup_telemetry

log = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan — startup and shutdown."""
    log.info("TradeFlow AI starting up", environment=settings.ENVIRONMENT)

    # Initialize Sentry
    if settings.SENTRY_DSN:
        sentry_sdk.init(
            dsn=settings.SENTRY_DSN,
            traces_sample_rate=0.2,
            profiles_sample_rate=0.1,
            environment=settings.ENVIRONMENT,
        )

    # Initialize Supabase client
    await init_supabase()

    log.info("TradeFlow AI ready", version="1.0.0")
    yield

    # Shutdown
    await close_supabase()
    log.info("TradeFlow AI shutdown complete")


def create_app() -> FastAPI:
    app = FastAPI(
        title="TradeFlow AI API",
        description="Predictive Customs Intelligence Platform — Cikarang Dry Port",
        version="1.0.0",
        docs_url="/docs" if settings.ENVIRONMENT != "production" else None,
        redoc_url="/redoc" if settings.ENVIRONMENT != "production" else None,
        lifespan=lifespan,
    )

    # Setup OpenTelemetry & Prometheus (Phase 6)
    setup_telemetry(app)

    # ── Middleware ────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(GZipMiddleware, minimum_size=1000)

    # ── Routers ───────────────────────────────────────────────────
    app.include_router(batches.router, prefix="/api/v1", tags=["batches"])
    app.include_router(hs_recommend.router, prefix="/api/v1", tags=["hs-recommend"])
    app.include_router(blockchain.router, prefix="/api/v1", tags=["blockchain"])
    app.include_router(admin.router, prefix="/api/v1/admin", tags=["admin"])

    # ── Prometheus metrics ────────────────────────────────────────
    Instrumentator(
        should_group_status_codes=True,
        should_ignore_untemplated=True,
    ).instrument(app).expose(app, endpoint="/metrics")

    # ── OpenTelemetry ─────────────────────────────────────────────
    if settings.OTEL_ENABLED:
        FastAPIInstrumentor().instrument_app(app)

    return app


app = create_app()


@app.get("/health", tags=["health"])
async def health_check() -> dict[str, str]:
    """Health check endpoint — public, no auth required."""
    return {"status": "ok", "version": "1.0.0", "environment": settings.ENVIRONMENT}
