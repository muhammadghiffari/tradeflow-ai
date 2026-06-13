"""
TradeFlow AI — Status Poller + Learning Nodes (T-060, T-065)
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from ..state import DeclarationState

logger = logging.getLogger("agents.poller")


async def poll_status_node(state: DeclarationState) -> dict:
    """Poll CEISA for PIB status (Celery beat task drives timing)."""
    from ....api.src.config import settings  # type: ignore
    from ....api.src.services.ceisa_client import CEISAClient

    aju = state.get("ceisa_aju", "")
    if not aju:
        return {
            "ceisa_response": {"status": "NOT_SUBMITTED"},
            "messages": [],
        }

    client = CEISAClient(settings)
    try:
        data = await client.get_status(aju)
        return {
            "ceisa_response": data,
            "messages": [{
                "node": "poll_status",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "event_type": "ceisa_status_polled",
                "payload": {"aju": aju, "status": data.get("status")},
            }],
        }
    except Exception as e:
        logger.error(f"CEISA status poll failed: {e}")
        return {
            "ceisa_response": {"status": "POLL_ERROR", "error": str(e)},
            "messages": [],
        }


async def record_outcome_node(state: DeclarationState) -> dict:
    """
    Record learning outcome (T-065):
    - Store final CEISA status in learning_outcomes table
    - Trigger model drift check
    - If correction count > threshold, trigger XGBoost retrain
    """
    from ....api.src.config import settings  # type: ignore

    batch_id = state.get("batch_id", "unknown")
    ceisa_status = state.get("ceisa_response", {}).get("status", "UNKNOWN")
    corrections = state.get("operator_corrections", [])
    approved = ceisa_status == "ACCEPTED"

    try:
        from ....api.src.tasks.learning_tasks import record_learning_outcome  # type: ignore
        await record_learning_outcome(
            batch_id=batch_id,
            approved=approved,
            ceisa_status=ceisa_status,
            corrections=corrections,
            crs_score=state.get("crs", {}).get("score"),
            rejection_probability=state.get("rejection_prediction", {}).get("probability"),
        )
    except Exception as e:
        logger.error(f"Failed to record learning outcome: {e}")

    return {
        "learning_feedback": {
            "corrections_recorded": len(corrections),
            "outcome": ceisa_status,
            "batch_id": batch_id,
        },
        "messages": [{
            "node": "record_outcome",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": "outcome_recorded",
            "payload": {
                "batch_id": batch_id,
                "ceisa_status": ceisa_status,
                "corrections_count": len(corrections),
                "approved": approved,
            },
        }],
    }
