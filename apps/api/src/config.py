"""
TradeFlow AI — Application Configuration (T-004)

SDD §2.1 + PRD §22 Invariant: No bare os.getenv().
ALL environment variables are validated here via pydantic-settings.
This is the SINGLE source of truth for configuration.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import AnyHttpUrl, Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Application ───────────────────────────────────────────────────────────
    ENVIRONMENT: Literal["development", "staging", "production"] = "development"
    DEBUG: bool = False
    SECRET_KEY: SecretStr = Field(..., min_length=32)
    CORS_ORIGINS: list[str] = ["*"]

    # ── Database ──────────────────────────────────────────────────────────────
    DATABASE_URL: str  # asyncpg connection string e.g. postgresql+asyncpg://...

    # ── Supabase ──────────────────────────────────────────────────────────────
    SUPABASE_URL: str
    SUPABASE_ANON_KEY: str
    SUPABASE_SERVICE_KEY: SecretStr
    SUPABASE_JWT_SECRET: SecretStr

    # ── Keycloak 26 — SOLE auth provider (Invariant #4) ───────────────────────
    KEYCLOAK_SERVER_URL: str
    KEYCLOAK_REALM: str = "tradeflow"
    KEYCLOAK_CLIENT_ID: str = "tradeflow-api"
    KEYCLOAK_CLIENT_SECRET: SecretStr
    KEYCLOAK_ISSUER: str

    @property
    def KEYCLOAK_JWKS_URL(self) -> str:
        base = self.KEYCLOAK_SERVER_URL.rstrip("/")
        return f"{base}/realms/{self.KEYCLOAK_REALM}/protocol/openid-connect/certs"

    # ── Redis 8 Standalone ────────────────────────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_CELERY_DB: int = 0
    REDIS_CACHE_DB: int = 1

    # ── AI Inference Services (SDD §2.3–2.6) ─────────────────────────────────
    CLOUD_LLM_ONLY: bool = False                                    # Bypass heavy local models and use Gemini API instead
    SURYA_INFERENCE_URL: AnyHttpUrl = "http://surya-svc:8001"       # Agent A
    OLM_INFERENCE_URL: AnyHttpUrl = "http://olm-inference:8000"     # Agent D
    PADDLEOCR_SVC_URL: AnyHttpUrl = "http://paddleocr-svc:8002"     # Agent B
    MINERU_SVC_URL: AnyHttpUrl = "http://mineru-svc:8003"           # Preprocessor
    OLM_BASE_MODEL: str = "allenai/olmOCR-2-7B-1025"
    OLM_LORA_ADAPTER: str = "muhammadghiffari/olm-ocr-cipl-v1"
    HF_TOKEN: SecretStr = ""  # type: ignore[assignment]

    # ── Azure Document Intelligence — Agent C ─────────────────────────────────
    AZURE_DI_ENDPOINT: AnyHttpUrl = ""  # type: ignore[assignment]
    AZURE_DI_KEY: SecretStr = ""  # type: ignore[assignment]
    AZURE_DI_FREE_LIMIT: int = 5000   # Pages/month on F0 tier (Invariant #9)

    # ── CEISA (Simulator in dev, real endpoint in prod) ───────────────────────
    CEISA_BASE_URL: AnyHttpUrl = "http://simulator:8006"
    CEISA_CLIENT_ID: str = ""
    CEISA_CLIENT_SECRET: SecretStr = ""  # type: ignore[assignment]
    CEISA_REQUEST_TIMEOUT_SECONDS: int = 30
    CEISA_POLL_INTERVAL_SECONDS: int = 30
    CEISA_AES_KEY: SecretStr = ""  # type: ignore[assignment]  # AES-256-GCM key for payload encryption (base64)

    # ── Blockchain ────────────────────────────────────────────────────────────
    ENABLE_BLOCKCHAIN: bool = True
    OPERATOR_WALLET_PRIVATE_KEY: SecretStr = ""  # type: ignore[assignment]  # Never log!
    POLYGON_RPC_URL: str = "https://rpc-amoy.polygon.technology"
    CONTRACT_ADDRESS: str = ""
    PINATA_JWT: SecretStr = ""  # type: ignore[assignment]
    POLYGON_MAX_FEE_GWEI: int = 80
    POLYGON_MAX_PRIORITY_FEE_GWEI: int = 3
    POLYGON_ANCHOR_GAS_LIMIT: int = 250_000

    # ── Notifications ─────────────────────────────────────────────────────────
    RESEND_API_KEY: SecretStr = ""  # type: ignore[assignment]
    WHATSAPP_TOKEN: SecretStr = ""  # type: ignore[assignment]
    WHATSAPP_PHONE_NUMBER_ID: str = ""
    NOTIFICATION_EMAIL_FROM: str = "noreply@tradeflow.ai"

    # ── ChromaDB ──────────────────────────────────────────────────────────────
    CHROMADB_HOST: str = "localhost"
    CHROMADB_PORT: int = 8000

    # ── AI / LLM ─────────────────────────────────────────────────────────────
    GEMINI_API_KEY: SecretStr = Field(..., description="Google Gemini API key")
    GEMINI_MODEL_PRIMARY: str = "gemini-3.1-pro"
    GEMINI_MODEL_FALLBACK: str = "gemini-3.5-flash"
    OPENAI_API_KEY: SecretStr = ""  # type: ignore[assignment]
    EMBEDDING_MODEL: str = "text-embedding-3-small"

    # LangSmith tracing
    LANGCHAIN_TRACING_V2: bool = True
    LANGCHAIN_PROJECT: str = "tradeflow-ai"
    LANGCHAIN_API_KEY: SecretStr = ""  # type: ignore[assignment]

    # ── Feature Flags ─────────────────────────────────────────────────────────
    ENABLE_SURYA_AGENT: bool = True
    ENABLE_AZURE_DI_AGENT: bool = True
    ENABLE_VESSEL_VALIDATION: bool = True
    ENABLE_BLOCKCHAIN: bool = True  # type: ignore[assignment] — redeclared intentionally
    ENABLE_INSW_CHECK: bool = True
    ENABLE_NOTIFICATIONS_WHATSAPP: bool = False
    ENABLE_ADAPTIVE_LEARNING: bool = True
    ENABLE_AI_COPILOT: bool = True
    ENABLE_HS_RAG: bool = True
    ENABLE_REJECTION_PREDICTION: bool = True
    ENABLE_STATUS_POLLING: bool = True
    ENABLE_MARITIME_DATA_FEATURES: bool = True
    DETERMINISTIC_E2E: bool = False  # Used in extract.py to swap LLM for deterministic mock

    # ── Thresholds ────────────────────────────────────────────────────────────
    OCR_FAST_PATH_QUALITY_THRESHOLD: float = 0.95
    OCR_RECONCILIATION_DISAGREEMENT_THRESHOLD: float = 0.20
    LLM_CONFIDENCE_REVIEW_THRESHOLD: float = 0.70
    CRS_MIN_SUBMIT_THRESHOLD: int = 55
    HS_CONFIDENCE_RAG_THRESHOLD: float = 0.75
    XGB_MIN_SAMPLES_FOR_MODEL: int = 500
    MAX_RESUBMIT_ATTEMPTS: int = 5
    REJECTION_RISK_BLOCK_THRESHOLD: float = 0.70

    # ── Validation rules ──────────────────────────────────────────────────────
    VALIDATION_RULES_PATH: str = "packages/db/validation_rules.json"
    CARRIER_PROFILES_PATH: str = "packages/db/carrier_profiles.json"
    XGBOOST_MODEL_PATH: str = "models/rejection_predictor.json"

    # ── Adaptive learning / drift ─────────────────────────────────────────────
    RETRAIN_MIN_NEW_SAMPLES: int = 100
    RETRAIN_MIN_TOTAL_SAMPLES: int = 500
    DRIFT_LOOKBACK_DAYS: int = 30
    DRIFT_CORRECTION_THRESHOLD: int = 50

    # ── Celery ────────────────────────────────────────────────────────────────
    CELERY_TASK_SOFT_TIME_LIMIT: int = 300
    CELERY_TASK_TIME_LIMIT: int = 600

    # ── Observability ─────────────────────────────────────────────────────────
    SENTRY_DSN: str = ""
    POSTHOG_API_KEY: str = ""
    OTEL_ENABLED: bool = False
    OTEL_EXPORTER_OTLP_ENDPOINT: str = ""

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: str | list[str]) -> list[str]:
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v

    @field_validator("DEBUG", mode="before")
    @classmethod
    def parse_debug(cls, v: bool | str) -> bool:
        if isinstance(v, str) and v.lower() in {"release", "prod", "production"}:
            return False
        return bool(v)


class CeleryConfig:
    """Celery configuration — separate class for Celery's config_from_object."""
    task_serializer = "json"
    result_serializer = "json"
    accept_content = ["json"]
    timezone = "Asia/Jakarta"
    enable_utc = True
    task_soft_time_limit = 300
    task_time_limit = 600
    task_acks_late = True           # Ack only after successful completion (NFR-016)
    worker_prefetch_multiplier = 1  # One task at a time per worker


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]


settings = get_settings()
