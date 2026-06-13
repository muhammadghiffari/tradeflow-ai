"""
TradeFlow AI — FastAPI Dependencies

Auth (Keycloak JWT), DB session, tier/role guards.
PRD §4 Decision 2: Keycloak 26 is the ONLY auth provider.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Annotated
import time

import httpx
import structlog
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from jose.exceptions import ExpiredSignatureError
try:
    from supabase import AsyncClient, acreate_client
except Exception:  # pragma: no cover - optional in lightweight test environments
    AsyncClient = None
    acreate_client = None

from .config import settings

log = structlog.get_logger()

# ── Supabase client (singleton) ───────────────────────────────────────────────
_supabase_client: AsyncClient | None = None


async def init_supabase() -> None:
    global _supabase_client
    if acreate_client is None:
        log.info("Supabase client not available in this environment; skipping initialization")
        _supabase_client = None
        return

    _supabase_client = await acreate_client(
        settings.SUPABASE_URL,
        settings.SUPABASE_SERVICE_KEY.get_secret_value(),  # Service key for server-side ops
    )
    log.info("Supabase client initialized")


async def close_supabase() -> None:
    global _supabase_client
    if _supabase_client:
        await _supabase_client.aclose()
        _supabase_client = None


def get_supabase() -> AsyncClient:
    if _supabase_client is None:
        raise RuntimeError("Supabase client not initialized. Call init_supabase() first.")
    return _supabase_client


# ── Keycloak JWKS cache ───────────────────────────────────────────────────────
_keycloak_jwks: dict | None = None
_keycloak_jwks_time: float = 0
KEYCLOAK_JWKS_TTL = 3600  # Refresh every hour


def get_keycloak_jwks() -> dict:
    """Fetch Keycloak JWKS with TTL-based caching (refresh every hour)."""
    global _keycloak_jwks, _keycloak_jwks_time
    now = time.time()
    
    if not _keycloak_jwks or (now - _keycloak_jwks_time) > KEYCLOAK_JWKS_TTL:
        with httpx.Client() as client:
            response = client.get(settings.KEYCLOAK_JWKS_URL)
            response.raise_for_status()
            _keycloak_jwks = response.json()
            _keycloak_jwks_time = now
            log.info("Refreshed Keycloak JWKS cache")
    
    return _keycloak_jwks


# ── JWT Bearer scheme ─────────────────────────────────────────────────────────
bearer_scheme = HTTPBearer(auto_error=True)


class CurrentUser:
    """Decoded Keycloak JWT claims, enriched with Supabase profile."""

    def __init__(
        self,
        sub: str,
        email: str,
        full_name: str,
        roles: list[str],
        tier: str,
        company_id: str | None,
        raw_token: str,
    ) -> None:
        self.id = sub
        self.sub = sub
        self.email = email
        self.full_name = full_name
        self.roles = roles
        self.tier = tier
        self.company_id = company_id
        self.raw_token = raw_token

    @property
    def is_enterprise(self) -> bool:
        return self.tier == "enterprise"

    @property
    def is_admin(self) -> bool:
        return "admin" in self.roles or "supervisor" in self.roles

    @property
    def role(self) -> str:
        """Primary role (first in list)."""
        return self.roles[0] if self.roles else "operator"


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(bearer_scheme)],
    supabase: Annotated[AsyncClient, Depends(get_supabase)],
) -> CurrentUser:
    """
    Validate Keycloak RS256 JWT and return enriched user.
    PRD §4 Decision 2: verify against Keycloak JWKS endpoint.
    """
    token = credentials.credentials

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired authentication token",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        jwks = get_keycloak_jwks()
        payload = jwt.decode(
            token,
            jwks,
            algorithms=["RS256"],
            audience=settings.KEYCLOAK_CLIENT_ID,
            issuer=settings.KEYCLOAK_ISSUER,
        )
    except ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except JWTError as e:
        log.warning("JWT validation failed", error=str(e))
        raise credentials_exception

    sub: str = payload.get("sub", "")
    if not sub:
        raise credentials_exception

    # Extract Keycloak realm roles
    realm_access = payload.get("realm_access", {})
    roles: list[str] = realm_access.get("roles", [])
    # Filter to only TradeFlow roles
    tradeflow_roles = [r for r in roles if r in ("operator", "admin", "supervisor", "importer")]

    # Fetch profile from Supabase for tier + company_id
    try:
        result = await supabase.table("profiles").select(
            "id, full_name, email, tier, role, company_id"
        ).eq("id", sub).single().execute()
        profile = result.data
        tier = profile.get("tier", "sme")
        company_id = profile.get("company_id")
        full_name = profile.get("full_name", payload.get("name", ""))
        email = profile.get("email", payload.get("email", ""))
    except Exception:
        # Profile not yet created — use JWT claims as fallback
        tier = "sme"
        company_id = sub  # Fallback to user's own ID so they can act as their own company
        full_name = payload.get("name", "")
        email = payload.get("email", "")

    return CurrentUser(
        sub=sub,
        email=email,
        full_name=full_name,
        roles=tradeflow_roles if tradeflow_roles else ["operator"],
        tier=tier,
        company_id=company_id,
        raw_token=token,
    )


# ── Role/tier guards ──────────────────────────────────────────────────────────

async def require_enterprise(
    user: Annotated[CurrentUser, Depends(get_current_user)],
) -> CurrentUser:
    """Guard: Enterprise tier only."""
    if not user.is_enterprise:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This feature requires an Enterprise tier subscription.",
        )
    return user


async def require_admin(
    user: Annotated[CurrentUser, Depends(get_current_user)],
) -> CurrentUser:
    """Guard: Admin or Supervisor role only."""
    if not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This action requires Administrator or Supervisor role.",
        )
    return user


async def require_operator(
    user: Annotated[CurrentUser, Depends(get_current_user)],
) -> CurrentUser:
    """Guard: Any authenticated user with operator/admin/supervisor role."""
    if "importer" in user.roles and len(user.roles) == 1:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Importers cannot perform operator actions.",
        )
    return user
