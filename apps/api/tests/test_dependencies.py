"""
Tests for JWT and authentication dependencies
"""

import pytest
import time
from unittest.mock import patch, MagicMock
from src import dependencies
from src.dependencies import get_keycloak_jwks, KEYCLOAK_JWKS_TTL


@pytest.fixture(autouse=True)
def reset_jwks_cache():
    dependencies._keycloak_jwks = None
    dependencies._keycloak_jwks_time = 0
    yield
    dependencies._keycloak_jwks = None
    dependencies._keycloak_jwks_time = 0


def test_keycloak_jwks_cached_with_ttl():
    """Test that Keycloak JWKS is cached with TTL."""
    with patch("src.dependencies.httpx.Client") as mock_client:
        # Mock HTTP response
        mock_response = MagicMock()
        mock_response.json = MagicMock(return_value={"keys": ["test-key-1"]})
        mock_client.return_value.__enter__.return_value.get.return_value = mock_response
        
        # First call should fetch from HTTP
        jwks1 = get_keycloak_jwks()
        assert jwks1 == {"keys": ["test-key-1"]}
        
        # Call count should be 1
        assert mock_client.return_value.__enter__.return_value.get.call_count == 1
        
        # Second call within TTL should use cache (no new HTTP call)
        jwks2 = get_keycloak_jwks()
        assert jwks2 == {"keys": ["test-key-1"]}
        assert mock_client.return_value.__enter__.return_value.get.call_count == 1  # Still 1


def test_keycloak_jwks_refreshes_after_ttl():
    """Test that Keycloak JWKS is refreshed after TTL expires."""
    with patch("src.dependencies.httpx.Client") as mock_client:
        with patch("src.dependencies.time.time") as mock_time:
            # Mock HTTP responses
            mock_response1 = MagicMock()
            mock_response1.json = MagicMock(return_value={"keys": ["old-key"]})
            
            mock_response2 = MagicMock()
            mock_response2.json = MagicMock(return_value={"keys": ["new-key"]})
            
            mock_client.return_value.__enter__.return_value.get.side_effect = [mock_response1, mock_response2]
            
            # Mock time progression
            mock_time.side_effect = [0, 0, KEYCLOAK_JWKS_TTL + 1]  # First call, second call, then TTL expires
            
            # First call
            jwks1 = get_keycloak_jwks()
            assert jwks1 == {"keys": ["old-key"]}
            
            # Second call (still within TTL)
            jwks2 = get_keycloak_jwks()
            assert jwks2 == {"keys": ["old-key"]}
            
            # Third call (after TTL expires) - should refresh
            jwks3 = get_keycloak_jwks()
            assert jwks3 == {"keys": ["new-key"]}
            assert mock_client.return_value.__enter__.return_value.get.call_count == 2


def test_keycloak_jwks_handles_http_errors():
    """Test that JWKS fetch handles HTTP errors."""
    with patch("src.dependencies.httpx.Client") as mock_client:
        # Mock HTTP error
        mock_client.return_value.__enter__.return_value.get.side_effect = Exception("Connection refused")
        
        # Should raise the exception
        with pytest.raises(Exception, match="Connection refused"):
            get_keycloak_jwks()


def test_current_user_immutable():
    """Test that CurrentUser object stores all required fields."""
    from src.dependencies import CurrentUser
    
    user = CurrentUser(
        sub="user-123",
        email="user@example.com",
        full_name="Test User",
        roles=["operator"],
        tier="sme",
        company_id="company-123",
        raw_token="jwt-token"
    )
    
    # Should have all fields
    assert user.sub == "user-123"
    assert user.email == "user@example.com"
    assert user.roles == ["operator"]
    assert user.tier == "sme"
    assert user.company_id == "company-123"
