"""
TradeFlow AI — Keycloak 26 JWT Authentication (T-008)

PRD Invariant #4: Keycloak 26 is the SOLE auth provider. No Supabase Auth.
Validates JWTs via JWKS endpoint with a 5-minute cache.
"""

from __future__ import annotations

import time
from typing import Any

import httpx
from fastapi import HTTPException, status
from jose import JWTError, jwk, jwt

from ..config import settings

# JWKS TTL — 5 minutes (SDD §4.1)
_JWKS_TTL_SECONDS = 300


class JWKSCache:
    """Thread-safe JWKS cache with 5-minute TTL."""

    def __init__(self) -> None:
        self._keys: dict[str, Any] = {}
        self._fetched_at: float = 0.0

    def _is_stale(self) -> bool:
        return time.monotonic() - self._fetched_at > _JWKS_TTL_SECONDS

    async def get_keys(self) -> dict[str, Any]:
        if not self._keys or self._is_stale():
            await self._refresh()
        return self._keys

    async def _refresh(self) -> None:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(settings.KEYCLOAK_JWKS_URL)
            resp.raise_for_status()
            jwks_data = resp.json()

        # Build kid → key mapping
        self._keys = {}
        for key_data in jwks_data.get("keys", []):
            kid = key_data.get("kid")
            if kid:
                self._keys[kid] = jwk.construct(key_data)

        self._fetched_at = time.monotonic()


_jwks_cache = JWKSCache()


async def verify_keycloak_token(token: str) -> dict[str, Any]:
    """
    Verify a Keycloak JWT token.

    Returns the decoded payload (claims) on success.
    Raises HTTP 401 on any failure.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        # Step 1: Decode header to get kid without signature verification
        unverified_header = jwt.get_unverified_header(token)
    except JWTError:
        raise credentials_exception

    kid = unverified_header.get("kid")
    if not kid:
        raise credentials_exception

    # Step 2: Get the signing key from JWKS cache
    try:
        keys = await _jwks_cache.get_keys()
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Auth service temporarily unavailable",
        )

    signing_key = keys.get(kid)
    if not signing_key:
        # Key not found — JWKS may have rotated, force refresh
        await _jwks_cache._refresh()
        keys = await _jwks_cache.get_keys()
        signing_key = keys.get(kid)
        if not signing_key:
            raise credentials_exception

    # Step 3: Verify signature + claims
    try:
        payload = jwt.decode(
            token,
            signing_key,
            algorithms=["RS256"],
            audience=settings.KEYCLOAK_CLIENT_ID,
            issuer=settings.KEYCLOAK_ISSUER,
            options={"verify_exp": True},
        )
    except JWTError as e:
        raise credentials_exception from e

    return payload


def extract_roles(payload: dict[str, Any]) -> list[str]:
    """Extract realm-level roles from a decoded Keycloak token."""
    realm_access = payload.get("realm_access", {})
    return realm_access.get("roles", [])


def extract_user_id(payload: dict[str, Any]) -> str:
    """Extract the user UUID (Keycloak sub claim)."""
    sub = payload.get("sub")
    if not sub:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing subject claim",
        )
    return sub
