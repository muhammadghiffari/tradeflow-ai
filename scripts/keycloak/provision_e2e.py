"""Provision a Keycloak client + user for E2E tests and fetch a user token.

Usage (example):

  SET KEYCLOAK_SERVER_URL=http://localhost:8080
  SET KEYCLOAK_ADMIN=admin
  SET KEYCLOAK_ADMIN_PASSWORD=admin1234
  python scripts\keycloak\provision_e2e.py

Outputs a small env file at `.env.e2e` with `E2E_BEARER_TOKEN`.

Notes:
- Requires Keycloak admin API to be reachable and the admin credentials to be valid.
- The script is idempotent: it will reuse existing client/user if present.
"""
from __future__ import annotations

import os
import sys
import time
import json
from typing import Optional

import requests


def _fail(msg: str) -> str:
    """Fail fast if a required environment variable is missing."""
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(1)


KEYCLOAK_URL = os.getenv("KEYCLOAK_SERVER_URL", "http://localhost:8080")
ADMIN_USER = os.getenv("KEYCLOAK_ADMIN") or _fail("KEYCLOAK_ADMIN env var is required")
ADMIN_PASS = os.getenv("KEYCLOAK_ADMIN_PASSWORD") or _fail("KEYCLOAK_ADMIN_PASSWORD env var is required")
REALM = os.getenv("KEYCLOAK_REALM", "tradeflow")

CLIENT_ID = "tradeflow-e2e-client"
USERNAME = "e2e-user"
PASSWORD = os.getenv("E2E_USER_PASSWORD") or _fail("E2E_USER_PASSWORD env var is required")


def admin_token() -> str:
    url = f"{KEYCLOAK_URL.rstrip('/')}/realms/master/protocol/openid-connect/token"
    resp = requests.post(url, data={
        "grant_type": "password",
        "client_id": "admin-cli",
        "username": ADMIN_USER,
        "password": ADMIN_PASS,
    })
    resp.raise_for_status()
    return resp.json()["access_token"]


def find_client(admin_tok: str) -> Optional[dict]:
    url = f"{KEYCLOAK_URL.rstrip('/')}/admin/realms/{REALM}/clients"
    headers = {"Authorization": f"Bearer {admin_tok}", "Content-Type": "application/json"}
    resp = requests.get(url, headers=headers)
    resp.raise_for_status()
    for c in resp.json():
        if c.get("clientId") == CLIENT_ID:
            return c
    return None


def create_client(admin_tok: str) -> dict:
    existing = find_client(admin_tok)
    if existing:
        return existing

    url = f"{KEYCLOAK_URL.rstrip('/')}/admin/realms/{REALM}/clients"
    headers = {"Authorization": f"Bearer {admin_tok}", "Content-Type": "application/json"}
    payload = {
        "clientId": CLIENT_ID,
        "publicClient": False,
        "directAccessGrantsEnabled": True,
        "protocol": "openid-connect",
        "redirectUris": ["*"],
    }
    resp = requests.post(url, headers=headers, data=json.dumps(payload))
    if resp.status_code not in (201, 204):
        resp.raise_for_status()

    # Keycloak returns Location header with created client's internal id
    loc = resp.headers.get("Location")
    if not loc:
        # fallback: re-query
        return find_client(admin_tok)
    client_id = loc.rstrip('/').split('/')[-1]
    # fetch client representation
    info = requests.get(f"{KEYCLOAK_URL.rstrip('/')}/admin/realms/{REALM}/clients/{client_id}", headers=headers)
    info.raise_for_status()
    return info.json()


def get_client_secret(admin_tok: str, client_internal_id: str) -> str:
    url = f"{KEYCLOAK_URL.rstrip('/')}/admin/realms/{REALM}/clients/{client_internal_id}/client-secret"
    headers = {"Authorization": f"Bearer {admin_tok}", "Content-Type": "application/json"}
    resp = requests.get(url, headers=headers)
    resp.raise_for_status()
    return resp.json().get("value")


def find_user(admin_tok: str) -> Optional[dict]:
    url = f"{KEYCLOAK_URL.rstrip('/')}/admin/realms/{REALM}/users"
    headers = {"Authorization": f"Bearer {admin_tok}", "Content-Type": "application/json"}
    resp = requests.get(url, headers=headers, params={"username": USERNAME})
    resp.raise_for_status()
    users = resp.json()
    return users[0] if users else None


def create_user(admin_tok: str) -> dict:
    existing = find_user(admin_tok)
    if existing:
        return existing

    url = f"{KEYCLOAK_URL.rstrip('/')}/admin/realms/{REALM}/users"
    headers = {"Authorization": f"Bearer {admin_tok}", "Content-Type": "application/json"}
    payload = {"username": USERNAME, "enabled": True, "emailVerified": True}
    resp = requests.post(url, headers=headers, data=json.dumps(payload))
    if resp.status_code not in (201, 204):
        resp.raise_for_status()
    # Get created user
    return find_user(admin_tok)


def set_user_password(admin_tok: str, user_id: str) -> None:
    url = f"{KEYCLOAK_URL.rstrip('/')}/admin/realms/{REALM}/users/{user_id}/reset-password"
    headers = {"Authorization": f"Bearer {admin_tok}", "Content-Type": "application/json"}
    payload = {"type": "password", "temporary": False, "value": PASSWORD}
    resp = requests.put(url, headers=headers, data=json.dumps(payload))
    resp.raise_for_status()


def request_token(client_id: str, client_secret: str = None) -> str:
    url = f"{KEYCLOAK_URL.rstrip('/')}/realms/{REALM}/protocol/openid-connect/token"
    data = {
        "grant_type": "password",
        "client_id": client_id,
        "username": USERNAME,
        "password": PASSWORD,
    }
    if client_secret:
        data["client_secret"] = client_secret
    resp = requests.post(url, data=data)
    resp.raise_for_status()
    return resp.json().get("access_token")


def main() -> int:
    print("Provisioning Keycloak E2E client/user...")
    admin_tok = admin_token()
    client = create_client(admin_tok)
    client_internal_id = client.get("id")
    secret = get_client_secret(admin_tok, client_internal_id)

    user = create_user(admin_tok)
    user_id = user.get("id")
    set_user_password(admin_tok, user_id)

    # Allow Keycloak to synchronize
    time.sleep(1)

    token = request_token(CLIENT_ID, secret)

    # Write a small .env file for use with tests
    with open(".env.e2e", "w", encoding="utf-8") as fh:
        fh.write(f"E2E_BEARER_TOKEN={token}\n")

    print("Wrote .env.e2e with E2E_BEARER_TOKEN. Use SET RUN_FULL_E2E=1 and run tests.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except requests.exceptions.RequestException as e:
        print("Keycloak provisioning failed:", e)
        sys.exit(2)
