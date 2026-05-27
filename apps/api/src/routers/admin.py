"""
TradeFlow AI — Admin Router
"""

from typing import Annotated, Any
from fastapi import APIRouter, Depends
import structlog

from ..dependencies import CurrentUser, require_admin

log = structlog.get_logger()
router = APIRouter()

@router.get("/analytics")
async def get_analytics(
    user: Annotated[CurrentUser, Depends(require_admin)]
) -> dict[str, Any]:
    """Get platform analytics for admin dashboard."""
    # Stub implementation
    return {
        "total_declarations": 150,
        "avg_crs": 82.5,
        "success_rate": 0.92,
        "avg_processing_time": 42.1
    }

@router.post("/retrain")
async def trigger_retrain(
    user: Annotated[CurrentUser, Depends(require_admin)]
) -> dict[str, Any]:
    """Manually trigger XGBoost retraining."""
    from ..tasks.learning_tasks import retrain_predictor
    retrain_predictor.apply_async(queue="low")
    return {"status": "enqueued"}
