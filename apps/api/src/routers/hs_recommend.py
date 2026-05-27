"""
TradeFlow AI — HS Recommendation Router
"""

from typing import Annotated, Any
from fastapi import APIRouter, Depends
from pydantic import BaseModel
import structlog

from ..dependencies import CurrentUser, get_current_user

log = structlog.get_logger()
router = APIRouter()

class HSRecommendRequest(BaseModel):
    product_description: str
    context: str | None = None

@router.post("/hs-recommend")
async def recommend_hs(
    request: HSRecommendRequest,
    user: Annotated[CurrentUser, Depends(get_current_user)]
) -> dict[str, Any]:
    """Get HS code recommendations for a product description."""
    # Stub implementation
    log.info("HS Recommendation requested", description=request.product_description)
    return {
        "recommendations": [
            {
                "hs_code": "8471.30.20",
                "description_id": "Mesin pengolah data otomatis portabel",
                "duty_rate": 0,
                "vat_rate": 0.11,
                "confidence": 0.95,
                "reasoning": "Product is a laptop."
            }
        ]
    }
