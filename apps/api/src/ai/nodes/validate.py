"""
TradeFlow AI — Cross-Document Validation Node (Step 2.4)
"""

import structlog

from ...services.validation_rules_svc import validation_rules_service
from ..state import ExtractionGraphState

log = structlog.get_logger()

async def validation_node(state: ExtractionGraphState) -> dict:
    """
    Step 2.4: Cross-Document Validation against JSON rules.
    """
    log.info("Running validation_node", batch_id=state["batch_id"])

    results, needs_review = validation_rules_service.evaluate(state)

    return {
        "validation_results": results,
        "needs_human_review": needs_review,
        "steps": ["validation"]
    }
