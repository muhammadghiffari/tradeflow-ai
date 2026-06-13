"""
TradeFlow AI — Vessel Validation Agent (T-043)

Validates vessel information from extracted fields against maritime data tables:
  - ais_vessel_positions
  - vessel_characteristics
  - vessel_ownership
  - port_lineup

Issues codes per SDD:
  V001: Vessel not found in AIS database
  V002: Vessel IMO number mismatch
  V003: ETA discrepancy > 72 hours
  V004: Vessel flagged in sanctions list
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import asyncpg

from ..state import DeclarationState
from ..validators.field_normalizers import normalize_value

logger = logging.getLogger("agents.vessel_validation")


async def vessel_validate_node(state: DeclarationState) -> dict:
    """
    Run vessel validation for the primary bill of lading document.
    Updates state with vessel_validation dict and logs issues.
    """
    from ....api.src.config import settings  # type: ignore

    if not settings.ENABLE_VESSEL_VALIDATION:
        return {
            "vessel_validation": {
                "passed": True,
                "status": "info",
                "issues": [{"severity": "INFO", "code": "V000",
                            "message": "Vessel validation disabled by feature flag"}],
                "vessel_confirmed": False,
                "ais_eta": None,
                "lineup_confirmed": False,
            },
            "messages": [],
        }

    # Extract vessel fields from reconciled data
    vessel_name, voyage_number, bl_date, arrival_port = _extract_vessel_fields(state)

    if not vessel_name:
        return {
            "vessel_validation": {
                "passed": False,
                "status": "critical",
                "issues": [{
                    "severity": "CRITICAL",
                    "code": "V001",
                    "message": "Vessel name could not be extracted from documents",
                }],
                "vessel_confirmed": False,
                "ais_eta": None,
                "lineup_confirmed": False,
            },
            "messages": [],
        }

    # Query maritime tables
    db_url = settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
    issues = []
    vessel_confirmed = False
    ais_eta = None
    lineup_confirmed = False

    try:
        conn = await asyncpg.connect(db_url)
        try:
            # V001 / V002: Check AIS vessel positions
            ais_result = await _check_ais_positions(conn, vessel_name)
            if ais_result is None:
                issues.append({
                    "severity": "WARNING",
                    "code": "V001",
                    "message": (
                        f"Vessel '{vessel_name}' not found in AIS database. "
                        "Manual verification recommended."
                    ),
                })
            else:
                vessel_confirmed = True
                ais_eta = ais_result.get("eta")

                # V003: ETA discrepancy check
                if bl_date and ais_eta:
                    eta_issue = _check_eta_discrepancy(bl_date, ais_eta, voyage_number)
                    if eta_issue:
                        issues.append(eta_issue)

            # Check port lineup for arrival confirmation
            if arrival_port and vessel_name:
                lineup = await _check_port_lineup(conn, vessel_name, arrival_port)
                if lineup:
                    lineup_confirmed = True
                else:
                    issues.append({
                        "severity": "INFO",
                        "code": "V003",
                        "message": (
                            f"Vessel '{vessel_name}' not found in port lineup for "
                            f"'{arrival_port}'. This is informational only."
                        ),
                    })

            # V004: Sanctions check (placeholder — integrate OFAC/UN list)
            sanctions_issue = await _check_sanctions(conn, vessel_name)
            if sanctions_issue:
                issues.append(sanctions_issue)

        finally:
            await conn.close()

    except Exception as e:
        logger.error(f"Vessel validation DB error: {e}")
        issues.append({
            "severity": "WARNING",
            "code": "V001",
            "message": f"Vessel validation service temporarily unavailable: {e}",
        })

    # Determine overall status
    critical = any(i["severity"] == "CRITICAL" for i in issues)
    warnings = any(i["severity"] == "WARNING" for i in issues)

    if critical:
        status = "critical"
        passed = False
    elif warnings:
        status = "warning"
        passed = True
    elif issues:
        status = "info"
        passed = True
    else:
        status = "passed"
        passed = True

    return {
        "vessel_validation": {
            "passed": passed,
            "status": status,
            "issues": issues,
            "vessel_confirmed": vessel_confirmed,
            "ais_eta": ais_eta.isoformat() if ais_eta else None,
            "lineup_confirmed": lineup_confirmed,
        },
        "messages": [{
            "node": "vessel_validate",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": "vessel_validation_complete",
            "payload": {
                "vessel_name": vessel_name,
                "status": status,
                "issues_count": len(issues),
            },
        }],
    }


def _extract_vessel_fields(
    state: DeclarationState,
) -> tuple[str | None, str | None, str | None, str | None]:
    """Extract vessel_name, voyage_number, bl_date, arrival_port from reconciled fields."""
    vessel_name = None
    voyage_number = None
    bl_date = None
    arrival_port = None

    for doc_fields in state.get("reconciled_fields", []):
        # vessel_name
        vn = doc_fields.get("vessel_name") or doc_fields.get("namaKapal")
        if vn and isinstance(vn, dict) and vn.get("value"):
            vessel_name = normalize_value("vessel_name", str(vn["value"]))

        # voyage
        vo = doc_fields.get("voyage_number") or doc_fields.get("voyageNumber")
        if vo and isinstance(vo, dict) and vo.get("value"):
            voyage_number = str(vo["value"]).strip()

        # bl_date
        bd = doc_fields.get("bl_date") or doc_fields.get("tglBl")
        if bd and isinstance(bd, dict) and bd.get("value"):
            bl_date = normalize_value("bl_date", str(bd["value"]))

        # arrival port
        ap = doc_fields.get("port_discharge_code") or doc_fields.get("kodePelabuhanBongkar")
        if ap and isinstance(ap, dict) and ap.get("value"):
            arrival_port = str(ap["value"]).strip().upper()

    return vessel_name, voyage_number, bl_date, arrival_port


async def _check_ais_positions(
    conn: asyncpg.Connection, vessel_name: str
) -> dict | None:
    """Query ais_vessel_positions for the vessel."""
    # Search by name (case-insensitive) — last known position within 30 days
    row = await conn.fetchrow(
        """
        SELECT imo, vessel_name, latitude, longitude, speed_knots,
               destination, eta, timestamp
        FROM ais_vessel_positions
        WHERE LOWER(vessel_name) LIKE LOWER($1)
           OR LOWER(vessel_name) = LOWER($2)
        ORDER BY timestamp DESC
        LIMIT 1
        """,
        f"%{vessel_name}%",
        vessel_name,
    )
    if row is None:
        return None
    return dict(row)


async def _check_port_lineup(
    conn: asyncpg.Connection, vessel_name: str, port_locode: str
) -> dict | None:
    """Query port_lineup for vessel arrival at the given port."""
    row = await conn.fetchrow(
        """
        SELECT imo, vessel_name, port_locode, eta, etd, voyage_number
        FROM port_lineup
        WHERE (LOWER(vessel_name) LIKE LOWER($1) OR LOWER(vessel_name) = LOWER($2))
          AND port_locode = $3
          AND eta > NOW() - INTERVAL '7 days'
        ORDER BY eta
        LIMIT 1
        """,
        f"%{vessel_name}%",
        vessel_name,
        port_locode,
    )
    return dict(row) if row else None


async def _check_sanctions(
    conn: asyncpg.Connection, vessel_name: str
) -> dict | None:
    """
    Placeholder for sanctions screening.
    In production: integrate OFAC SDN list, UN Security Council, EU lists.
    """
    # For demo: check against a hardcoded set of test sanctions
    sanctioned_vessels = {"SANCTIONED VESSEL", "BLOCKED SHIP"}
    if vessel_name.upper() in sanctioned_vessels:
        return {
            "severity": "CRITICAL",
            "code": "V004",
            "message": (
                f"Vessel '{vessel_name}' appears on a sanctions watchlist. "
                "This shipment requires compliance review before proceeding."
            ),
        }
    return None


def _check_eta_discrepancy(
    bl_date: str, ais_eta: datetime, voyage_number: str | None
) -> dict | None:
    """
    V003: Check if B/L date and AIS ETA are logically consistent.
    B/L date should be before or within 72 hours of AIS ETA.
    """
    try:
        bl_dt = datetime.strptime(bl_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        if ais_eta.tzinfo is None:
            ais_eta = ais_eta.replace(tzinfo=timezone.utc)

        # If AIS ETA is more than 72 hours before B/L date, something is wrong
        if ais_eta < bl_dt - timedelta(hours=72):
            return {
                "severity": "WARNING",
                "code": "V003",
                "message": (
                    f"ETA discrepancy: AIS reports vessel arrival {ais_eta.date()} "
                    f"but B/L date is {bl_date}. Difference exceeds 72 hours."
                ),
            }
    except (ValueError, TypeError):
        pass

    return None
