"""
TradeFlow AI — Remaining LangGraph nodes:
  - review_ready_node  (T-034 completion)
  - poll_status_node   (T-060 prep)
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from ..state import DeclarationState

logger = logging.getLogger("agents.nodes")


async def review_ready_node(state: DeclarationState) -> dict:
    """
    Set batch status to REVIEW_READY and trigger Supabase Realtime notification.
    The graph pauses at END after this node (interrupt_before=["submit"]).
    """
    from ....api.src.config import settings  # type: ignore

    batch_id = state.get("batch_id", "unknown")
    crs_score = state.get("crs", {}).get("score", 0)
    risk_level = state.get("rejection_prediction", {}).get("risk_level", "UNKNOWN")
    blocked = crs_score < settings.CRS_MIN_SUBMIT_THRESHOLD

    # Update batch status in database
    try:
        from ....api.src.db.database import get_async_session  # type: ignore
        async with get_async_session() as db:
            await db.execute(
                "UPDATE batches SET status = $1, crs_score = $2, rejection_probability = $3 WHERE id = $4",
                "REVIEW_READY",
                crs_score,
                state.get("rejection_prediction", {}).get("probability", 0.0),
                batch_id,
            )
    except Exception as e:
        logger.error(f"Failed to update batch status: {e}")

    return {
        "messages": [{
            "node": "review_ready",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": "review_ready",
            "payload": {
                "batch_id": batch_id,
                "crs_score": crs_score,
                "risk_level": risk_level,
                "blocked_by_crs": blocked,
            },
        }],
    }


async def ingest_node(state: DeclarationState) -> dict:
    """Validate documents list is populated. Entry point of graph."""
    documents = state.get("documents", [])
    if not documents:
        return {
            "error": "No documents provided in batch",
            "messages": [{
                "node": "ingest",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "event_type": "ingest_failed",
                "payload": {"reason": "empty_documents"},
            }],
        }
    return {
        "messages": [{
            "node": "ingest",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": "ingest_complete",
            "payload": {"document_count": len(documents)},
        }],
    }
