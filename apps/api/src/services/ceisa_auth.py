"""
TradeFlow AI — CEISA 4.0 OAuth 2.0 Token Manager (T-050)

Manages the OAuth 2.0 client_credentials token lifecycle for CEISA H2H.
  - Acquires token on first use
  - Caches in Redis with TTL = expires_in - 60s (safety margin)
  - Transparently refreshes on expiry

PRD: No bare os.getenv() — all config from settings.
"""
from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger("services.ceisa_auth")

_REDIS_KEY = "ceisa:oauth_token"


class CEISAAuthClient:
    """Thread-safe CEISA OAuth 2.0 token manager backed by Redis."""

    def __init__(self, settings: Any) -> None:
        self._settings = settings
        self._redis_url = settings.REDIS_URL

    async def _get_redis(self):
        import redis.asyncio as aioredis
        return await aioredis.from_url(self._redis_url, decode_responses=True)

    async def get_access_token(self) -> str:
        """Return a valid access token, acquiring a new one if needed."""
        r = await self._get_redis()
        try:
            token = await r.get(_REDIS_KEY)
            if token:
                return token
        finally:
            await r.aclose()

        return await self._acquire_token()

    async def _acquire_token(self) -> str:
        """Acquire a new token from CEISA OAuth endpoint and cache in Redis."""
        token_url = f"{self._settings.CEISA_BASE_URL.rstrip('/')}/auth/token"
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    token_url,
                    data={
                        "grant_type": "client_credentials",
                        "client_id": self._settings.CEISA_CLIENT_ID,
                        "client_secret": self._settings.CEISA_CLIENT_SECRET.get_secret_value(),
                    },
                )
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"CEISA token acquisition failed: {e.response.status_code}")
            raise
        except Exception as e:
            logger.error(f"CEISA token endpoint unreachable: {e}")
            raise

        token = data.get("access_token")
        expires_in = int(data.get("expires_in", 3600))
        ttl = max(expires_in - 60, 60)  # safety margin

        r = await self._get_redis()
        try:
            await r.setex(_REDIS_KEY, ttl, token)
        finally:
            await r.aclose()

        logger.info(f"CEISA access token acquired, TTL={ttl}s")
        return token

    async def invalidate(self) -> None:
        """Force token invalidation (e.g., after 401 response)."""
        r = await self._get_redis()
        try:
            await r.delete(_REDIS_KEY)
        finally:
            await r.aclose()
