"""
TradeFlow AI — Blockchain Router
"""

from typing import Annotated, Any
from fastapi import APIRouter, Depends
import structlog

from ..dependencies import CurrentUser, get_current_user

log = structlog.get_logger()
router = APIRouter()

@router.get("/blockchain/{batch_id}")
async def get_blockchain_receipt(
    batch_id: str,
    user: Annotated[CurrentUser, Depends(get_current_user)]
) -> dict[str, Any]:
    """Get blockchain anchoring receipt for a batch."""
    # Stub implementation
    return {
        "status": "pending",
        "tx_hash": None,
        "polygonscan_url": None,
        "ipfs_cid": None
    }
