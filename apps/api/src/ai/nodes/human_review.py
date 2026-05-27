"""
TradeFlow AI — Human Review Interrupt Node (Step 2.6)

PRD §0.2 Invariant #5: LangGraph's interrupt() is the ONLY mechanism
to pause execution for human review. No polling loops.
"""

from __future__ import annotations

import structlog
from langgraph.types import interrupt

from ..state import ExtractionGraphState

log = structlog.get_logger()


async def human_review_node(state: ExtractionGraphState) -> dict:
    """
    Pause the graph and surface extracted fields for operator review.

    The graph will resume when an operator POSTs to
    POST /api/v1/batches/{batch_id}/review with their corrections.

    `interrupt()` saves full graph state to Redis checkpoint store.
    """
    log.info(
        "Interrupting for human review",
        batch_id=state["batch_id"],
        risk_level=state.get("risk_level"),
    )

    # Surfaces the current extraction output to the operator
    review_payload = {
        "batch_id": state["batch_id"],
        "combined_data": state.get("combined_data", {}),
        "validation_results": state.get("validation_results", []),
        "risk_level": state.get("risk_level", "UNKNOWN"),
        "message": "Dokumen ini memerlukan tinjauan manual sebelum dapat diajukan.",
    }

    # PRD §10: interrupt() — execution suspends here.
    # The operator's corrections are returned as the `interrupt` return value.
    corrections: dict = interrupt(review_payload)

    # Merge operator corrections into combined_data
    corrected_data = {**state.get("combined_data", {}), **corrections}

    log.info(
        "Human review complete — resuming graph",
        batch_id=state["batch_id"],
        corrections_count=len(corrections),
    )

    return {
        "combined_data": corrected_data,
        "needs_human_review": False,
        "steps": ["human_review"],
    }
