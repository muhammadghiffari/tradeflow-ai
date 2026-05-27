"""
TradeFlow AI — Cross-Document Validation Node (Step 2.4)
"""

import structlog
from ..state import ExtractionGraphState

log = structlog.get_logger()

async def validation_node(state: ExtractionGraphState) -> dict:
    """
    Step 2.4: Cross-Document Validation against JSON rules.
    """
    log.info("Running validation_node", batch_id=state["batch_id"])
    
    data = state.get("combined_data", {})
    results = []
    needs_review = False
    
    # Stub: check total_packages from BL vs PL
    # Real implementation would evaluate rules in validation_rules.json
    bl_packages = data.get("total_packages")
    pl_packages = data.get("total_packages") # simulated identical for now
    
    if bl_packages != pl_packages:
        results.append({
            "rule_id": "CV001",
            "severity": "CRITICAL_FAIL",
            "message": "Package Count Consistency Failed"
        })
        needs_review = True
    else:
        results.append({
            "rule_id": "CV001",
            "severity": "PASS",
            "message": "Package Count matches"
        })
        
    return {
        "validation_results": results,
        "needs_human_review": needs_review,
        "steps": ["validation"]
    }
