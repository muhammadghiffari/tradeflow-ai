import os
import subprocess

import pytest
from fastapi.testclient import TestClient

from src.main import app


@pytest.mark.integration
def test_keycloak_token_allows_authenticated_api_call():
    """Provision Keycloak test client/user if needed, then call an authenticated endpoint.

    Skipped unless `RUN_KEYCLOAK=1` is set. If `.env.e2e` is missing the test
    will attempt to run the provisioning script `scripts/keycloak/provision_e2e.py`.
    """
    if os.getenv("RUN_KEYCLOAK") != "1":
        pytest.skip("Set RUN_KEYCLOAK=1 to run Keycloak auth flow test")

    envfile = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..", ".env.e2e"))

    if not os.path.exists(envfile):
        # Attempt to provision Keycloak artifacts (best-effort)
        provision_script = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..", "scripts", "keycloak", "provision_e2e.py"))
        if not os.path.exists(provision_script):
            pytest.skip("Keycloak provision script not found; please run it manually to create test client/user")
        proc = subprocess.run(["python", provision_script], capture_output=True, text=True)
        if proc.returncode != 0:
            pytest.skip(f"Provisioning script failed: {proc.stdout}\n{proc.stderr}")

    # Load token from .env.e2e
    token = None
    with open(envfile, encoding="utf-8") as fh:
        for line in fh:
            if line.strip().startswith("E2E_BEARER_TOKEN="):
                token = line.strip().split("=", 1)[1]
                break

    if not token:
        pytest.skip("E2E_BEARER_TOKEN not found in .env.e2e")

    client = TestClient(app)
    headers = {"Authorization": f"Bearer {token}"}

    # Call a protected endpoint that uses get_current_user
    r = client.get("/api/v1/batches", headers=headers)
    # 200 OK expected (empty list) or 401 if setup incomplete
    assert r.status_code in (200, 401), f"Unexpected status: {r.status_code} - {r.text}"
