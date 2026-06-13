"""
TradeFlow AI — INSW Lartas Check Service (T-057)

Validates HS codes against INSW lartas (restricted goods) list
before CEISA submission.

In production: POST to INSW API
In dev/simulator: use hardcoded lartas rules by HS code prefix
"""
from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger("services.insw_check")

# Lartas HS code prefixes (simplified demo set)
# Production: query INSW Lartas API at https://www.insw.go.id/api
_LARTAS_PREFIXES: dict[str, list[str]] = {
    # BPOM: food, cosmetics, pharmaceuticals
    "01": ["SNI_REQUIRED", "BPOM_REGISTRATION"],
    "04": ["BPOM_REGISTRATION"],
    "21": ["BPOM_REGISTRATION"],
    "30": ["BPOM_REGISTRATION", "HALAL_CERTIFICATE"],
    # KEMENTAN: agricultural products
    "07": ["PHYTOSANITARY_CERTIFICATE", "KEMENTAN_APPROVAL"],
    "08": ["PHYTOSANITARY_CERTIFICATE"],
    "10": ["KEMENTAN_APPROVAL"],
    # MENLHK: CITES / endangered species
    "97": ["CITES_PERMIT"],
    # Weapons, explosives
    "93": ["POLRI_PERMIT"],
    # Electronics with SNI
    "85": ["SNI_REQUIRED"],
    "84": ["SNI_REQUIRED"],
    # Textiles
    "61": ["SNI_REQUIRED"],
    "62": ["SNI_REQUIRED"],
}


class INSWCheckService:
    def __init__(self, settings: Any) -> None:
        self._settings = settings

    async def check(self, hs_codes: list[str]) -> dict:
        """
        Check HS codes against INSW lartas restrictions.
        Returns: {passed: bool, issues: [str]}
        """
        if not self._settings.ENABLE_INSW_CHECK:
            return {"passed": True, "issues": [], "checked_codes": hs_codes}

        issues = []
        checked = []

        for hs in hs_codes:
            hs_clean = str(hs).strip().replace(".", "")[:8]
            if not hs_clean:
                continue
            checked.append(hs_clean)

            # Try real INSW API first
            api_result = await self._query_insw_api(hs_clean)
            if api_result is not None:
                if not api_result.get("free_to_trade", True):
                    issues.append(
                        f"HS {hs_clean}: {', '.join(api_result.get('restrictions', []))}"
                    )
            else:
                # Fallback: prefix-based rules
                prefix2 = hs_clean[:2]
                restrictions = _LARTAS_PREFIXES.get(prefix2)
                if restrictions:
                    issues.append(
                        f"HS {hs_clean} may require: {', '.join(restrictions)} "
                        "(verify via INSW portal)"
                    )

        return {
            "passed": len(issues) == 0,
            "issues": issues,
            "checked_codes": checked,
        }

    async def _query_insw_api(self, hs_code: str) -> dict | None:
        """Query real INSW lartas API. Returns None if unavailable."""
        insw_url = getattr(self._settings, "INSW_API_URL", None)
        if not insw_url:
            return None
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(
                    f"{insw_url}/lartas/check",
                    params={"hs_code": hs_code},
                )
                if resp.status_code == 200:
                    return resp.json()
        except Exception as e:
            logger.debug(f"INSW API unavailable: {e}")
        return None
