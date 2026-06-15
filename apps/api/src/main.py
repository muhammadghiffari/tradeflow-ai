"""
TradeFlow AI — FastAPI Application Entry Point

PRD §1.4 — Main application setup with lifespan management,
middleware, and router registration.
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

try:
    import sentry_sdk
except Exception:  # pragma: no cover - optional dependency for observability
    sentry_sdk = None

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

try:
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
except Exception:  # pragma: no cover - optional
    FastAPIInstrumentor = None

try:
    from prometheus_fastapi_instrumentator import Instrumentator
except Exception:  # pragma: no cover - optional
    Instrumentator = None

from .config import settings
from .dependencies import close_supabase, init_supabase
from .routers import admin, batches, blockchain, hs_recommend, vessel
from .utils.telemetry import setup_telemetry

log = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
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
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization"],
        expose_headers=["Content-Length"],
        max_age=3600,
    )
    app.add_middleware(GZipMiddleware, minimum_size=1000)

    # Rate limiting middleware (optional)
    try:
        from slowapi import Limiter
        from slowapi.util import get_remote_address
        limiter = Limiter(key_func=get_remote_address)
        app.state.limiter = limiter
    except Exception:
        app.state.limiter = None

    # ── Routers ───────────────────────────────────────────────────
    app.include_router(batches.router, prefix="/api/v1", tags=["batches"])
    app.include_router(hs_recommend.router, prefix="/api/v1", tags=["hs-recommend"])
    app.include_router(blockchain.router, prefix="/api/v1", tags=["blockchain"])
    app.include_router(vessel.router)
    app.include_router(admin.router, prefix="/api/v1/admin", tags=["admin"])

    # ── Prometheus metrics (optional) ────────────────────────────
    if Instrumentator is not None:
        Instrumentator(
            should_group_status_codes=True,
            should_ignore_untemplated=True,
        ).instrument(app).expose(app, endpoint="/metrics")

    # ── OpenTelemetry (optional) ─────────────────────────────────
    if settings.OTEL_ENABLED and FastAPIInstrumentor is not None:
        FastAPIInstrumentor().instrument_app(app)

    return app


app = create_app()


@app.get("/health", tags=["health"])
async def health_check() -> dict[str, str]:
    """Health check endpoint — public, no auth required."""
    return {"status": "ok", "version": "1.0.0", "environment": settings.ENVIRONMENT}
