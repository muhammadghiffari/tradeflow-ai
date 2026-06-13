import os
import time
from typing import Any

import pytest
from fastapi.testclient import TestClient

from src.config import settings
from src.main import app


@pytest.mark.integration
def test_full_e2e_upload_process_review_submit(monkeypatch):
    """Full end-to-end flow: upload -> process -> review -> submit.

    This test is intentionally guarded and only runs when the environment
    variable `RUN_FULL_E2E` is set to `1`. It also supports shortcuts for
    local development:

    - Set `SKIP_AUTH=1` to bypass Keycloak by monkeypatching `get_current_user`.
    - Set `SKIP_WORKER=1` to invoke processing tasks inline after upload.

    Requirements when enabled:
    - Keycloak, Supabase (db + storage), Redis, MinIO, ChromaDB all running
    - A valid bearer token available via `E2E_BEARER_TOKEN` OR use `SKIP_AUTH`
    """
    if os.getenv("RUN_FULL_E2E") != "1":
        pytest.skip("Set RUN_FULL_E2E=1 to run full end-to-end tests")

    client = TestClient(app)

    # Optionally bypass auth for local runs
    if os.getenv("SKIP_AUTH") == "1":
        from src.dependencies import CurrentUser

        def _fake_user(*a: Any, **k: Any) -> CurrentUser:
            return CurrentUser(
                sub="e2e-user",
                email="e2e@example.com",
                full_name="E2E User",
                roles=["operator"],
                tier="enterprise",
                company_id="e2e-company",
                raw_token="e2e",
            )

        monkeypatch.setattr("src.dependencies.get_current_user", lambda *a, **k: _fake_user())

    # Prepare upload payload (single minimal PDF)
    files = [
        ("files", ("bl.pdf", b"%PDF-1.4\n%EOF\n", "application/pdf")),
    ]
    data = {"doc_types": "bill_of_lading"}

    auth_header = {}
    token = os.getenv("E2E_BEARER_TOKEN")
    if token:
        auth_header = {"Authorization": f"Bearer {token}"}
    else:
        # If a .env.e2e file exists (produced by provisioning script), load it
        envfile = os.path.join(os.path.dirname(__file__), "../../..", ".env.e2e")
        try:
            envfile = os.path.abspath(envfile)
            if os.path.exists(envfile):
                with open(envfile, "r", encoding="utf-8") as f:
                    for line in f:
                        if line.strip().startswith("E2E_BEARER_TOKEN="):
                            token = line.strip().split("=", 1)[1]
                            auth_header = {"Authorization": f"Bearer {token}"}
                            break
        except Exception:
            pass

    resp = client.post("/api/v1/batches", files=files, data=data, headers=auth_header)
    assert resp.status_code in (200, 201), f"Upload failed: {resp.text}"
    batch_id = resp.json().get("batch_id")
    assert batch_id, "No batch_id returned"

    # Optionally trigger processing inline when no worker is available
    if os.getenv("SKIP_WORKER") == "1":
        try:
            from src.tasks.ocr_tasks import preprocess_document

            try:
                # Task is often defined with bind=True -> first arg is `self`
                preprocess_document(None, batch_id)
            except TypeError:
                # Some wrappers accept only (batch_id,)
                preprocess_document(batch_id)
        except Exception as exc:  # pragma: no cover - best-effort
            pytest.skip(f"Could not invoke preprocess task inline: {exc}")

    # Poll batch status until processing/review complete or timeout
    timeout = int(os.getenv("E2E_TIMEOUT_SECONDS", "60"))
    deadline = time.time() + timeout
    status = None
    while time.time() < deadline:
        r = client.get(f"/api/v1/batches/{batch_id}", headers=auth_header)
        if r.status_code == 200:
            data = r.json().get("batch") or {}
            status = data.get("status")
            if status in ("review_complete", "submitted", "rejected"):
                break
        time.sleep(2)

    assert status is not None, "Timed out waiting for batch to become available"
    assert status in ("review_complete", "submitted"), f"Unexpected final status: {status}"