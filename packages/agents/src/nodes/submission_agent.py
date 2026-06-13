"""
TradeFlow AI — Submission Agent (T-059)

LangGraph nodes for the post-approval pipeline:
  build_payload_node  → assemble PIB JSON
  insw_check_node     → lartas validation
  submit_node         → H2H PIB submission (HitL interrupt point)
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from ..state import DeclarationState
from ..utils.pib_builder import build_pib_payload

logger = logging.getLogger("agents.submission")


async def build_payload_node(state: DeclarationState) -> dict:
    """Build the CEISA PIB JSON payload from reconciled state."""
    try:
        payload = build_pib_payload(state)
        return {
            "ceisa_payload": payload,
            "messages": [{
                "node": "build_payload",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "event_type": "payload_built",
                "payload": {"field_count": len(payload)},
            }],
        }
    except Exception as e:
        logger.error(f"PIB build failed: {e}")
        return {
            "ceisa_payload": {},
            "error": str(e),
            "messages": [],
        }


async def insw_check_node(state: DeclarationState) -> dict:
    """Run INSW lartas check for all HS codes in the payload."""
    from ....api.src.config import settings  # type: ignore
    from ....api.src.services.insw_check_svc import INSWCheckService

    payload = state.get("ceisa_payload", {})
    hs_codes = [
        item.get("posTarif", "")
        for item in payload.get("barang", [])
        if item.get("posTarif")
    ]

    svc = INSWCheckService(settings)
    result = await svc.check(hs_codes)

    return {
        "insw_status": result,
        "messages": [{
            "node": "insw_check",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": "insw_check_complete",
            "payload": result,
        }],
    }


async def submit_node(state: DeclarationState) -> dict:
    """
    Submit PIB to CEISA. This node is reached ONLY after operator approval
    (graph resumes from interrupt_before=["submit"]).
    """
    from ....api.src.config import settings  # type: ignore
    from ....api.src.services.ceisa_client import CEISAClient

    attempt = (state.get("submission_attempt") or 0) + 1

    if attempt > settings.MAX_RESUBMIT_ATTEMPTS:
        return {
            "error": f"Maximum resubmission attempts ({settings.MAX_RESUBMIT_ATTEMPTS}) exceeded",
            "ceisa_response": {"status": "FAILED", "reason": "max_attempts_exceeded"},
            "messages": [],
        }

    payload = state.get("ceisa_payload", {})
    client = CEISAClient(settings)

    try:
        result = await client.submit_pib(payload)
        return {
            "ceisa_aju": result.get("aju_number", ""),
            "ceisa_reference": result.get("submission_id", ""),
            "ceisa_response": result.get("raw", result),
            "submission_attempt": attempt,
            "messages": [{
                "node": "submit",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "event_type": "pib_submitted",
                "payload": {
                    "aju_number": result.get("aju_number"),
                    "attempt": attempt,
                    "status": result.get("status"),
                },
            }],
        }
    except Exception as e:
        logger.error(f"PIB submission failed (attempt {attempt}): {e}")
        return {
            "error": str(e),
            "submission_attempt": attempt,
            "ceisa_response": {"status": "FAILED", "reason": str(e)},
            "messages": [{
                "node": "submit",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "event_type": "pib_submission_failed",
                "payload": {"attempt": attempt, "error": str(e)},
            }],
        }
