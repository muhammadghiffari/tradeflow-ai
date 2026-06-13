"""
TradeFlow AI — Blockchain Router
"""

from typing import Annotated, Any

import structlog
from fastapi import APIRouter, Depends, HTTPException

from ..dependencies import CurrentUser, get_current_user

log = structlog.get_logger()
router = APIRouter()

@router.get("/blockchain/{batch_id}")
async def get_blockchain_receipt(
    batch_id: str,
    user: Annotated[CurrentUser, Depends(get_current_user)],
) -> dict[str, Any]:
    """Get blockchain anchoring receipt for a batch.

    Requires: User must be in the same company as the batch.
    """

    from ..dependencies import get_supabase

    supabase = get_supabase()

    # Authorization check: User must own or have access to this batch
    batch_res = await supabase.table("batches").select("company_id").eq("id", batch_id).single().execute()

    if not batch_res.data:
        raise HTTPException(status_code=404, detail="Batch not found")

    batch = batch_res.data

    # Check: User's company matches batch company or user is admin
    if batch["company_id"] != user.company_id and not user.is_admin:
        log.warning("Unauthorized blockchain access attempt", batch_id=batch_id, user=user.id, company=user.company_id)
        raise HTTPException(status_code=403, detail="You don't have access to this batch")

    # Stub implementation
    return {
        "status": "pending",
        "tx_hash": None,
        "polygonscan_url": None,
        "ipfs_cid": None
    }
