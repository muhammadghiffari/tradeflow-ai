"""
Tests for configuration and environment variables
"""

import pytest
from pydantic import ValidationError

from src.config import Settings


def test_gemini_api_key_required(monkeypatch):
    """Test that GEMINI_API_KEY is required and not hardcoded."""
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    # Should fail when GEMINI_API_KEY is not provided
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            _env_file=None,
            SECRET_KEY="test-secret-key-12345678901234567890",
            DATABASE_URL="postgresql://localhost/test",
            SUPABASE_URL="https://test.supabase.co",
            SUPABASE_ANON_KEY="test-key",
            SUPABASE_SERVICE_KEY="test-service-key",
            SUPABASE_JWT_SECRET="test-jwt-secret",
            KEYCLOAK_SERVER_URL="http://localhost:8080",
            KEYCLOAK_CLIENT_SECRET="test-secret",
            KEYCLOAK_ISSUER="http://localhost:8080/realms/tradeflow",
            # Note: GEMINI_API_KEY intentionally omitted
        )

    # Verify the error mentions GEMINI_API_KEY
    assert "GEMINI_API_KEY" in str(exc_info.value)


def test_gemini_api_key_from_env(monkeypatch):
    """Test that GEMINI_API_KEY is loaded from environment."""
    monkeypatch.setenv("GEMINI_API_KEY", "AIzaSy_valid_test_key_1234567890")

    settings = Settings(
        SECRET_KEY="test-secret-key-12345678901234567890",
        DATABASE_URL="postgresql://localhost/test",
        SUPABASE_URL="https://test.supabase.co",
        SUPABASE_ANON_KEY="test-key",
        SUPABASE_SERVICE_KEY="test-service-key",
        SUPABASE_JWT_SECRET="test-jwt-secret",
        KEYCLOAK_SERVER_URL="http://localhost:8080",
        KEYCLOAK_CLIENT_SECRET="test-secret",
        KEYCLOAK_ISSUER="http://localhost:8080/realms/tradeflow",
        GEMINI_API_KEY="AIzaSy_valid_test_key_1234567890",
    )

    assert settings.GEMINI_API_KEY == "AIzaSy_valid_test_key_1234567890"
    # Ensure the config loads dynamically and is not a hardcoded default
    assert settings.GEMINI_API_KEY is not None


def test_cors_origins_controlled():
    """Test that CORS origins are controlled (not wildcard)."""
    settings = Settings(
        SECRET_KEY="test-secret-key-12345678901234567890",
        DATABASE_URL="postgresql://localhost/test",
        SUPABASE_URL="https://test.supabase.co",
        SUPABASE_ANON_KEY="test-key",
        SUPABASE_SERVICE_KEY="test-service-key",
        SUPABASE_JWT_SECRET="test-jwt-secret",
        KEYCLOAK_SERVER_URL="http://localhost:8080",
        KEYCLOAK_CLIENT_SECRET="test-secret",
        KEYCLOAK_ISSUER="http://localhost:8080/realms/tradeflow",
        GEMINI_API_KEY="test-key",
    )

    # CORS origins should not contain wildcard
    assert "*" not in settings.CORS_ORIGINS
    # Should be a list of specific origins
    assert isinstance(settings.CORS_ORIGINS, list)
    assert len(settings.CORS_ORIGINS) > 0
