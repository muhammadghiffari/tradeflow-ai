"""
TradeFlow AI — Vessel Validation Router (T-070)

GET /api/v1/vessel/validate?vessel_name=...&voyage=...
POST /api/v1/vessel/validate  (full validation with batch context)
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from ..auth.dependencies import RequireOperator, get_current_user, CurrentUser

router = APIRouter(prefix="/api/v1", tags=["vessel"])


class VesselValidateRequest(BaseModel):
    vessel_name: str
    voyage_number: str | None = None
    bl_date: str | None = None
    arrival_port: str | None = None
    batch_id: str | None = None


@router.get("/vessel/validate")
async def validate_vessel_quick(
    vessel_name: str = Query(..., description="Vessel name to validate"),
    voyage: str | None = Query(None, description="Voyage number"),
    _: None = RequireOperator,
) -> dict:
    """Quick vessel lookup — checks AIS database for vessel confirmation."""
    from ..services.ceisa_auth import CEISAAuthClient  # noqa: F401 (unused — intentional stub)
    import asyncpg
    from ..config import settings

    db_url = settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
    try:
        conn = await asyncpg.connect(db_url)
        row = await conn.fetchrow(
            """
            SELECT imo, vessel_name, latitude, longitude, speed_knots, timestamp
            FROM ais_vessel_positions
            WHERE LOWER(vessel_name) LIKE LOWER($1)
            ORDER BY timestamp DESC LIMIT 1
            """,
            f"%{vessel_name}%",
        )
        await conn.close()
        if row:
            return {
                "found": True,
                "vessel_name": row["vessel_name"],
                "imo": row["imo"],
                "last_position": {
                    "lat": row["latitude"],
                    "lon": row["longitude"],
                    "speed_knots": row["speed_knots"],
                    "timestamp": row["timestamp"].isoformat() if row["timestamp"] else None,
                },
            }
        return {"found": False, "vessel_name": vessel_name}
    except Exception as e:
        return {"found": False, "error": str(e)}


@router.post("/vessel/validate")
async def validate_vessel_full(
    body: VesselValidateRequest,
    user: Annotated[CurrentUser, Depends(get_current_user)],
) -> dict:
    """Full vessel validation with AIS + port lineup checks."""
    from packages.agents.src.nodes.vessel_validation_agent import vessel_validate_node  # type: ignore
    from ..config import settings

    # Build minimal state for the vessel_validate_node
    mock_state = {
        "batch_id": body.batch_id or "adhoc",
        "reconciled_fields": [{
            "vessel_name": {"value": body.vessel_name, "confidence": 1.0},
            "voyage_number": {"value": body.voyage_number, "confidence": 1.0} if body.voyage_number else None,
            "bl_date": {"value": body.bl_date, "confidence": 1.0} if body.bl_date else None,
            "port_discharge_code": {"value": body.arrival_port, "confidence": 1.0} if body.arrival_port else None,
        }],
        "preprocessed": [],
    }

    result = await vessel_validate_node(mock_state)
    return result.get("vessel_validation", {})
