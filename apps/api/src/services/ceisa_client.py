"""
TradeFlow AI — CEISA 4.0 H2H Client (T-051, T-052, T-053)

Handles:
  T-051: PIB submission + status polling
  T-052: Retry logic with exponential backoff + circuit breaker
  T-053: AJU number extraction and parsing
"""
from __future__ import annotations

import asyncio
import logging
import re
import time
from typing import Any

import httpx

from .ceisa_auth import CEISAAuthClient

logger = logging.getLogger("services.ceisa_client")

# Circuit breaker state
_circuit_open = False
_circuit_open_until: float = 0.0
_CIRCUIT_OPEN_SECONDS = 60  # back-off window
_CIRCUIT_FAILURE_THRESHOLD = 3
_consecutive_failures = 0


class CEISAClient:
    """
    CEISA 4.0 H2H PIB submission client.
    Implements exponential backoff + circuit breaker (T-052).
    """

    MAX_RETRIES = 3
    INITIAL_DELAY = 2.0  # seconds
    MAX_DELAY = 30.0
    BACKOFF_FACTOR = 2.0

    def __init__(self, settings: Any) -> None:
        self._settings = settings
        self._auth = CEISAAuthClient(settings)
        self._base_url = settings.CEISA_BASE_URL.rstrip("/")
        self._timeout = settings.CEISA_REQUEST_TIMEOUT_SECONDS

    def _check_circuit(self) -> None:
        global _circuit_open, _circuit_open_until
        if _circuit_open and time.monotonic() < _circuit_open_until:
            raise RuntimeError(
                f"CEISA circuit breaker OPEN. Retry in "
                f"{int(_circuit_open_until - time.monotonic())}s"
            )
        if _circuit_open and time.monotonic() >= _circuit_open_until:
            _circuit_open = False
            logger.info("CEISA circuit breaker CLOSED (retry window expired)")

    def _record_failure(self) -> None:
        global _consecutive_failures, _circuit_open, _circuit_open_until
        _consecutive_failures += 1
        if _consecutive_failures >= _CIRCUIT_FAILURE_THRESHOLD:
            _circuit_open = True
            _circuit_open_until = time.monotonic() + _CIRCUIT_OPEN_SECONDS
            logger.error(
                f"CEISA circuit breaker OPENED after {_consecutive_failures} failures"
            )

    def _record_success(self) -> None:
        global _consecutive_failures
        _consecutive_failures = 0

    async def _request(
        self, method: str, path: str, **kwargs
    ) -> httpx.Response:
        """
        Make an authenticated CEISA HTTP request with retry + backoff.
        On 401: refresh token and retry once.
        On 5xx/timeout: exponential backoff up to MAX_RETRIES.
        """
        self._check_circuit()
        token = await self._auth.get_access_token()
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        url = f"{self._base_url}{path}"

        delay = self.INITIAL_DELAY
        last_error: Exception | None = None

        for attempt in range(1, self.MAX_RETRIES + 2):  # +1 for token refresh attempt
            try:
                async with httpx.AsyncClient(timeout=float(self._timeout)) as client:
                    resp = await client.request(method, url, headers=headers, **kwargs)

                if resp.status_code == 401:
                    # Token expired — invalidate cache and retry once
                    await self._auth.invalidate()
                    token = await self._auth.get_access_token()
                    headers["Authorization"] = f"Bearer {token}"
                    continue

                if resp.status_code in (502, 503, 504):
                    logger.warning(f"CEISA {resp.status_code} on attempt {attempt}")
                    self._record_failure()
                    if attempt <= self.MAX_RETRIES:
                        await asyncio.sleep(min(delay, self.MAX_DELAY))
                        delay *= self.BACKOFF_FACTOR
                        continue
                    resp.raise_for_status()

                self._record_success()
                return resp

            except (httpx.TimeoutException, httpx.ConnectError) as e:
                logger.warning(f"CEISA connection error attempt {attempt}: {e}")
                self._record_failure()
                last_error = e
                if attempt <= self.MAX_RETRIES:
                    await asyncio.sleep(min(delay, self.MAX_DELAY))
                    delay *= self.BACKOFF_FACTOR
                    continue

        raise RuntimeError(f"CEISA request failed after {self.MAX_RETRIES} retries: {last_error}")

    # ─────────────────────────────────────────────────────────
    # Public API
    # ─────────────────────────────────────────────────────────

    async def submit_pib(self, pib_payload: dict) -> dict:
        """
        POST /openapi/document — Submit PIB payload to CEISA.
        Returns: {aju_number, submission_id, status, message}
        """
        resp = await self._request("POST", "/openapi/document", json=pib_payload)
        if resp.status_code not in (200, 201, 202):
            resp.raise_for_status()

        data = resp.json()
        aju = extract_aju_number(data)
        logger.info(f"PIB submitted, AJU: {aju}, status: {data.get('status')}")
        return {
            "aju_number": aju,
            "submission_id": data.get("submissionId"),
            "status": data.get("status", "QUEUED"),
            "message": data.get("message", ""),
            "raw": data,
        }

    async def get_status(self, aju_number: str) -> dict:
        """
        GET /openapi/document/status/{aju} — Poll CEISA for PIB status.
        """
        resp = await self._request("GET", f"/openapi/document/status/{aju_number}")
        if resp.status_code == 404:
            return {"status": "NOT_FOUND", "aju_number": aju_number}
        resp.raise_for_status()
        return resp.json()


# ─────────────────────────────────────────────────────────────
# T-053: AJU number parser
# ─────────────────────────────────────────────────────────────

_AJU_PATTERN = re.compile(r"\d{18}")


def extract_aju_number(response_data: dict) -> str:
    """
    Extract AJU number from CEISA response.
    AJU format: 18 digits (KPBC 6 + YY 2 + MM 2 + SEQUENCE 8).
    """
    # Canonical field
    if "ajuNumber" in response_data:
        aju = str(response_data["ajuNumber"]).strip()
        if _AJU_PATTERN.fullmatch(aju):
            return aju

    # Search all string fields
    for value in response_data.values():
        if isinstance(value, str):
            match = _AJU_PATTERN.search(value)
            if match:
                return match.group()

    # Fallback: return raw or empty
    return response_data.get("ajuNumber", response_data.get("aju", ""))
