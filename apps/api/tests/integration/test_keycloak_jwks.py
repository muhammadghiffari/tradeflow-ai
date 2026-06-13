import os
import pytest

from src.config import settings
from src.dependencies import get_keycloak_jwks


@pytest.mark.integration
def test_keycloak_jwks_endpoint_available():
    """Fetch Keycloak JWKS — requires Keycloak running and configured.

    This test is skipped unless `RUN_KEYCLOAK=1` is set to avoid
    accidental calls in lightweight integration runs.
    """
    if os.getenv("RUN_KEYCLOAK") != "1":
        pytest.skip("Set RUN_KEYCLOAK=1 to run Keycloak JWKS integration test")

    jwks = get_keycloak_jwks()
    assert isinstance(jwks, dict)
    assert "keys" in jwks and isinstance(jwks["keys"], list)
    assert len(jwks["keys"]) > 0
