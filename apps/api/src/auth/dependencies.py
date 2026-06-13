"""
TradeFlow AI — FastAPI Auth Dependencies (T-009)

Provides reusable dependency functions for role-based access control.
All protected endpoints must use one of these dependencies.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .keycloak import extract_roles, extract_user_id, verify_keycloak_token

bearer_scheme = HTTPBearer(auto_error=True)


async def get_current_token_payload(
    credentials: Annotated[HTTPAuthorizationCredentials, Security(bearer_scheme)],
) -> dict[str, Any]:
    """Verify the Bearer JWT and return its decoded payload."""
    return await verify_keycloak_token(credentials.credentials)


async def get_current_user_id(
    payload: Annotated[dict[str, Any], Depends(get_current_token_payload)],
) -> str:
    """Returns the authenticated user's Keycloak sub (UUID)."""
    return extract_user_id(payload)


async def get_current_roles(
    payload: Annotated[dict[str, Any], Depends(get_current_token_payload)],
) -> list[str]:
    """Returns the list of Keycloak realm roles for the current user."""
    return extract_roles(payload)


def require_roles(*allowed_roles: str):
    """
    Dependency factory that enforces role-based access.

    Usage:
        @router.post("/submit")
        async def submit(
            _: None = Depends(require_roles("operator", "admin"))
        ):
    """

    async def _check_roles(
        roles: Annotated[list[str], Depends(get_current_roles)],
    ) -> None:
        if not any(role in roles for role in allowed_roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Required roles: {list(allowed_roles)}",
            )

    return Depends(_check_roles)


# Convenience singletons for common role checks
RequireOperator = require_roles("operator", "admin")
RequireAdmin = require_roles("admin")
RequireSME = require_roles("sme", "operator", "admin")
RequireSupervisor = require_roles("supervisor", "admin")


class CurrentUser:
    """Dependency class bundling user_id + roles in one inject."""

    def __init__(self, user_id: str, roles: list[str]) -> None:
        self.user_id = user_id
        self.roles = roles

    def has_role(self, *roles: str) -> bool:
        return any(r in self.roles for r in roles)

    def is_admin(self) -> bool:
        return "admin" in self.roles


async def get_current_user(
    user_id: Annotated[str, Depends(get_current_user_id)],
    roles: Annotated[list[str], Depends(get_current_roles)],
) -> CurrentUser:
    """Returns a CurrentUser object with id and roles."""
    return CurrentUser(user_id=user_id, roles=roles)
