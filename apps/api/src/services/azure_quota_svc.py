"""
TradeFlow AI — Azure DI Quota Service (T-038)

Tracks Azure Document Intelligence page consumption against the
F0 free tier limit (5000 pages/month per PRD Invariant #9).
Uses Redis for atomic counter across all workers.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

logger = logging.getLogger("services.azure_quota")

_REDIS_KEY_PREFIX = "azure_di_quota"


class AzureQuotaService:
    """
    Tracks Azure DI page consumption per calendar month in Redis.
    Counter key: azure_di_quota:YYYY-MM
    """

    def __init__(self) -> None:
        from ...config import settings  # type: ignore

        self._limit = settings.AZURE_DI_FREE_LIMIT
        self._redis_url = settings.REDIS_URL

    def _get_key(self) -> str:
        month = datetime.now(UTC).strftime("%Y-%m")
        return f"{_REDIS_KEY_PREFIX}:{month}"

    async def _get_redis(self):  # type: ignore
        import redis.asyncio as aioredis
        return await aioredis.from_url(self._redis_url, decode_responses=True)

    async def get_current_usage(self) -> int:
        """Return pages consumed this calendar month."""
        r = await self._get_redis()
        try:
            val = await r.get(self._get_key())
            return int(val) if val else 0
        finally:
            await r.aclose()

    async def check_available(self, pages: int = 1) -> bool:
        """Return True if `pages` pages can still be consumed this month."""
        usage = await self.get_current_usage()
        available = self._limit - usage
        if available < pages:
            logger.warning(
                f"Azure DI quota check: {usage}/{self._limit} pages used "
                f"this month. Requested {pages} pages — limit exceeded."
            )
            return False
        return True

    async def increment(self, pages: int = 1) -> int:
        """Atomically increment the monthly usage counter. Returns new total."""
        r = await self._get_redis()
        try:
            key = self._get_key()
            new_val = await r.incrby(key, pages)
            # Set TTL to 32 days (auto-expires old months)
            await r.expire(key, 32 * 24 * 3600)
            logger.info(f"Azure DI quota: {new_val}/{self._limit} pages used this month")
            return int(new_val)
        finally:
            await r.aclose()
