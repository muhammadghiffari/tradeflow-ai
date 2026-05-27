"""
TradeFlow AI — Application Configuration

PRD §0.2 Invariant #3: No bare os.getenv().
ALL environment variables must be validated here via pydantic-settings
with strict type annotations.
"""

from functools import lru_cache
from typing import Literal

from pydantic import AnyHttpUrl, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Application ───────────────────────────────────────────────
    ENVIRONMENT: Literal["development", "staging", "production"] = "development"
    DEBUG: bool = False
    SECRET_KEY: str = Field(..., min_length=32)
    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost"]

    # ── Database ──────────────────────────────────────────────────
    DATABASE_URL: str  # asyncpg connection string

    # ── Supabase ──────────────────────────────────────────────────
    SUPABASE_URL: str
    SUPABASE_ANON_KEY: str
    SUPABASE_SERVICE_KEY: str
    SUPABASE_JWT_SECRET: str

    # ── Keycloak (sole OIDC provider — PRD §4 Decision 2) ────────
    KEYCLOAK_SERVER_URL: AnyHttpUrl
    KEYCLOAK_REALM: str = "tradeflow"
    KEYCLOAK_CLIENT_ID: str = "tradeflow-api"
    KEYCLOAK_CLIENT_SECRET: str

    @property
    def KEYCLOAK_JWKS_URL(self) -> str:
        return f"{self.KEYCLOAK_SERVER_URL}/realms/{self.KEYCLOAK_REALM}/protocol/openid-connect/certs"

    @property
    def KEYCLOAK_ISSUER(self) -> str:
        return f"{self.KEYCLOAK_SERVER_URL}/realms/{self.KEYCLOAK_REALM}"

    # ── Redis 8 Standalone (Celery broker + LangGraph checkpointer)
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_CELERY_DB: int = 0
    REDIS_CACHE_DB: int = 1

    # ── Storage ───────────────────────────────────────────────────
    STORAGE_BACKEND: Literal["supabase", "minio"] = "minio"
    STORAGE_BUCKET_NAME: str = "tradeflow-documents"

    # MinIO (local dev)
    MINIO_ENDPOINT: str = "localhost:9000"
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin"
    MINIO_SECURE: bool = False
    MINIO_MODELS_PATH: str = "/models"

    # ── ChromaDB ──────────────────────────────────────────────────
    CHROMADB_HOST: str = "localhost"
    CHROMADB_PORT: int = 8000

    # ── AI / LLM ─────────────────────────────────────────────────
    GEMINI_API_KEY: str
    GEMINI_MODEL_PRIMARY: str = "gemini-2.0-flash-exp"  # Updated to available model
    GEMINI_MODEL_FALLBACK: str = "gemini-1.5-flash"
    COST_SAVING_MODE: bool = False

    OPENAI_API_KEY: str  # For text-embedding-3-small (HS RAG)
    EMBEDDING_MODEL: str = "text-embedding-3-small"

    # LangSmith tracing
    LANGCHAIN_TRACING_V2: bool = True
    LANGCHAIN_PROJECT: str = "tradeflow-ai"
    LANGCHAIN_API_KEY: str = ""

    # ── Azure Document Intelligence (fallback OCR) ────────────────
    ENABLE_AZURE_DI_FALLBACK: bool = True
    AZURE_DI_ENDPOINT: str = ""
    AZURE_DI_KEY: str = ""

    # ── Blockchain ────────────────────────────────────────────────
    ENABLE_BLOCKCHAIN: bool = True
    BLOCKCHAIN_PRIVATE_KEY: str = ""    # Never log this value
    POLYGON_AMOY_RPC_URL: str = "https://rpc-amoy.polygon.technology"
    POLYGON_POS_RPC_URL: str = "https://polygon-rpc.com"
    CONTRACT_ADDRESS: str = ""
    PINATA_API_KEY: str = ""
    PINATA_SECRET_KEY: str = ""

    # ── Notifications ─────────────────────────────────────────────
    RESEND_API_KEY: str = ""
    WHATSAPP_TOKEN: str = ""
    WHATSAPP_PHONE_ID: str = ""
    NOTIFICATION_EMAIL_FROM: str = "noreply@tradeflow.ai"

    # ── Observability ─────────────────────────────────────────────
    SENTRY_DSN: str = ""
    POSTHOG_API_KEY: str = ""
    OTEL_ENABLED: bool = False
    OTEL_EXPORTER_OTLP_ENDPOINT: str = ""

    # ── Feature Flags ─────────────────────────────────────────────
    ENABLE_WHATSAPP_NOTIFICATIONS: bool = False
    ENABLE_ADAPTIVE_LEARNING: bool = True
    CRS_MIN_SUBMIT_THRESHOLD: float = 70.0

    # ── OCR Thresholds ────────────────────────────────────────────
    OCR_FALLBACK_TRIGGER_CONFIDENCE: float = 0.78
    OCR_FALLBACK_TRIGGER_QUALITY: float = 0.65
    HS_CODE_CONFIDENCE_THRESHOLD: float = 0.75

    # ── Celery ────────────────────────────────────────────────────
    CELERY_TASK_SOFT_TIME_LIMIT: int = 300   # 5 min
    CELERY_TASK_TIME_LIMIT: int = 600         # 10 min hard limit

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: str | list[str]) -> list[str]:
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v


class CeleryConfig:
    """Celery configuration — separate class for Celery's config_from_object."""
    broker_url: str
    result_backend: str
    task_serializer = "json"
    result_serializer = "json"
    accept_content = ["json"]
    timezone = "Asia/Jakarta"
    enable_utc = True
    task_soft_time_limit = 300
    task_time_limit = 600
    task_acks_late = True
    worker_prefetch_multiplier = 1
    task_track_started = True


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]


settings = get_settings()
