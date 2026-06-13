"""
TradeFlow AI — Pytest Fixtures and Shared Test Utilities
"""

from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

# Avoid importing the full `supabase` package at import time to keep
# local test runs lightweight (pyiceberg build can fail on Windows).
try:
    from supabase import AsyncClient as _AsyncClient
except Exception:  # pragma: no cover - best-effort import
    _AsyncClient = None

from src.dependencies import CurrentUser
from src.main import app


@pytest.fixture
def test_client():
    """FastAPI test client."""
    return TestClient(app)


@pytest.fixture
def mock_current_user():
    """Mock authenticated user (operator tier)."""
    return CurrentUser(
        sub="test-user-123",
        email="operator@example.com",
        full_name="Test Operator",
        roles=["operator"],
        tier="sme",
        company_id="company-123",
        raw_token="mock-jwt-token",
    )


@pytest.fixture
def mock_admin_user():
    """Mock authenticated admin user."""
    return CurrentUser(
        sub="admin-user-456",
        email="admin@example.com",
        full_name="Test Admin",
        roles=["admin"],
        tier="enterprise",
        company_id="admin-company",
        raw_token="mock-admin-jwt-token",
    )


@pytest.fixture
def mock_supabase():
    """Mock Supabase AsyncClient."""
    # Use spec when available, otherwise fall back to a plain AsyncMock
    client = AsyncMock(spec=_AsyncClient) if _AsyncClient is not None else AsyncMock()
    return client


@pytest.fixture
def mock_get_current_user(mock_current_user):
    """Patch get_current_user dependency."""
    return AsyncMock(return_value=mock_current_user)


@pytest.fixture
def mock_get_supabase(mock_supabase):
    """Patch get_supabase dependency."""
    return AsyncMock(return_value=mock_supabase)


@pytest.fixture
def sample_pdf_bytes():
    """Sample PDF file bytes for testing."""
    # Minimal PDF header (magic number)
    return b"%PDF-1.4\n%test content\n"


@pytest.fixture
def sample_image_bytes():
    """Sample PNG image bytes for testing."""
    # PNG magic number: 89 50 4E 47
    return b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"


@pytest.fixture
def sample_malicious_bytes():
    """Sample bytes with wrong magic number (e.g., EXE claiming to be PDF)."""
    # EXE magic number: MZ
    return b"MZ\x90\x00" + b"PDF" * 100


@pytest.fixture
def sample_batch_response():
    """Sample batch from Supabase."""
    return {
        "id": "batch-123",
        "created_by": "test-user-123",
        "company_id": "company-123",
        "status": "uploaded",
        "created_at": "2026-05-30T10:00:00Z",
        "expires_at": "2026-06-30T10:00:00Z",
    }
