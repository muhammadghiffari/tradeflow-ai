"""
TradeFlow AI — CEISA 4.0 PIA Simulator (T-061)

Faithfully mirrors the CEISA H2H PIA API for development/testing.
Supports 6 deterministic scenarios triggered by special fields.

Scenarios:
  1. ACCEPTED        — batch.ceisa_aju starts with "010100" → accepted
  2. REJECTED_AUTO   — description contains "AUTO_FIX" → reject then auto-fix loop
  3. REJECTED_MANUAL — description contains "MANUAL_FIX" → reject, needs operator
  4. PENDING_LONG    — description contains "SLOW" → 3 polls before terminal
  5. GATEWAY_TIMEOUT — nomorBl starts with "TIMEOUT" → 503 for 2 attempts
  6. INVALID_SCHEMA  — posTarif = "0000" → schema validation failure

Endpoints mirror CEISA PIA protocol:
  POST /openapi/document           → Submit PIB
  GET  /openapi/document/status/{aju} → Poll status
  GET  /health                     → Health check
  POST /admin/reset                → Reset scenario state (dev only)

Usage: docker-compose up simulator
"""

from __future__ import annotations

import asyncio
import hashlib
import random
import string
import time
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

app = FastAPI(
    title="CEISA 4.0 PIA Simulator",
    description="Development simulator for CEISA H2H integration testing",
    version="1.0.0",
)

# ─────────────────────────────────────────────────────────────
# In-memory state
# ─────────────────────────────────────────────────────────────
_submissions: dict[str, dict] = {}
_poll_counts: dict[str, int] = defaultdict(int)
_timeout_counts: dict[str, int] = defaultdict(int)


# ─────────────────────────────────────────────────────────────
# Schemas
# ─────────────────────────────────────────────────────────────
class PIBSubmitRequest(BaseModel):
    """Minimal PIB payload fields needed for scenario detection."""
    kodeDokumen: str = "20"
    ajuNumber: str = ""
    nomorBl: str = ""
    barang: list[dict] = []
    namaKapal: str = ""
    entitas: list[dict] = []


# ─────────────────────────────────────────────────────────────
# AJU Number Generator
# ─────────────────────────────────────────────────────────────
def generate_aju_number(kpbc_code: str = "050100") -> str:
    """
    Generate a realistic AJU number.
    Format: KPBC_CODE + YEAR(2) + MONTH(2) + SEQUENCE(6)
    Example: 050100260600123456
    """
    now = datetime.now(timezone.utc)
    year = now.strftime("%y")
    month = now.strftime("%m")
    seq = "".join(random.choices(string.digits, k=6))
    return f"{kpbc_code}{year}{month}{seq}"


# ─────────────────────────────────────────────────────────────
# Scenario detection
# ─────────────────────────────────────────────────────────────
def detect_scenario(payload: dict) -> str:
    """Detect which scenario to simulate based on payload content."""
    aju = payload.get("ajuNumber", "")
    bl_number = payload.get("nomorBl", "")
    barang = payload.get("barang", [])
    uraian = " ".join(b.get("uraian", "") for b in barang).upper()
    pos_tarif = " ".join(b.get("posTarif", "") for b in barang)

    if bl_number.startswith("TIMEOUT"):
        return "GATEWAY_TIMEOUT"
    if "0000" in pos_tarif:
        return "INVALID_SCHEMA"
    if "AUTO_FIX" in uraian:
        return "REJECTED_AUTO"
    if "MANUAL_FIX" in uraian:
        return "REJECTED_MANUAL"
    if "SLOW" in uraian:
        return "PENDING_LONG"

    return "ACCEPTED"  # Default: success


# ─────────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────────
@app.post("/openapi/document")
async def submit_pib(request: Request) -> JSONResponse:
    """
    PIB submission endpoint. Mirrors CEISA PIA POST /openapi/document.
    """
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    scenario = detect_scenario(body)
    bl_number = body.get("nomorBl", "SIM-BL-DEFAULT")
    submission_id = str(uuid.uuid4())
    aju_number = generate_aju_number()

    # Scenario: GATEWAY_TIMEOUT
    if scenario == "GATEWAY_TIMEOUT":
        bl = body.get("nomorBl", "")
        _timeout_counts[bl] += 1
        if _timeout_counts[bl] <= 2:
            # Simulate slow response
            await asyncio.sleep(0.5)
            return JSONResponse(
                status_code=503,
                content={"error": "gateway_timeout", "message": "CEISA gateway timeout"},
            )
        # 3rd attempt succeeds
        scenario = "ACCEPTED"

    # Scenario: INVALID_SCHEMA
    if scenario == "INVALID_SCHEMA":
        return JSONResponse(
            status_code=422,
            content={
                "status": "REJECTED",
                "errorCode": "E_PIB_001",
                "errorMessage": "Kode HS tidak valid: 00000000 tidak ditemukan dalam BTKI",
                "errorClassification": "OPERATOR_REQUIRED",
                "submissionId": submission_id,
            },
        )

    # Store submission
    _submissions[aju_number] = {
        "submissionId": submission_id,
        "ajuNumber": aju_number,
        "scenario": scenario,
        "status": "QUEUED",
        "nomorBl": bl_number,
        "submittedAt": datetime.now(timezone.utc).isoformat(),
        "body": body,
        "pollCount": 0,
    }

    return JSONResponse(
        status_code=200,
        content={
            "status": "QUEUED",
            "ajuNumber": aju_number,
            "submissionId": submission_id,
            "message": "Dokumen PIB diterima dan sedang diproses",
            "estimatedProcessingTime": "30-120 detik",
        },
    )


@app.get("/openapi/document/status/{aju_number}")
async def get_status(aju_number: str) -> JSONResponse:
    """
    Status polling endpoint. Mirrors CEISA PIA GET /openapi/document/status/{aju}.
    """
    submission = _submissions.get(aju_number)
    if not submission:
        raise HTTPException(status_code=404, detail=f"AJU {aju_number} not found")

    submission["pollCount"] += 1
    poll_count = submission["pollCount"]
    scenario = submission["scenario"]

    # Scenario state machine
    if scenario == "ACCEPTED":
        if poll_count >= 2:
            return JSONResponse({
                "ajuNumber": aju_number,
                "status": "ACCEPTED",
                "ceiSaReference": f"PIB-{aju_number}-ACCEPTED",
                "message": "PIB diterima dan telah mendapat nomor pendaftaran",
                "beaNumber": f"BEA-{aju_number}",
                "acceptedAt": datetime.now(timezone.utc).isoformat(),
            })

    elif scenario == "REJECTED_AUTO":
        if poll_count == 1:
            return JSONResponse({
                "ajuNumber": aju_number,
                "status": "REJECTED",
                "errorCode": "E_VAL_012",
                "errorMessage": "NIB importir tidak ditemukan di sistem OSS",
                "errorClassification": "AUTO_RECOVERABLE",
                "message": "Sistem akan mencoba perbaikan otomatis",
            })
        elif poll_count >= 3:
            return JSONResponse({
                "ajuNumber": aju_number,
                "status": "ACCEPTED",
                "ceiSaReference": f"PIB-{aju_number}-AUTO-FIXED",
                "message": "PIB berhasil diperbaiki dan diterima secara otomatis",
                "acceptedAt": datetime.now(timezone.utc).isoformat(),
            })

    elif scenario == "REJECTED_MANUAL":
        if poll_count >= 2:
            return JSONResponse({
                "ajuNumber": aju_number,
                "status": "REJECTED",
                "errorCode": "E_HS_007",
                "errorMessage": "Kode HS 39269090 memerlukan dokumen lartas (SNI)",
                "errorClassification": "OPERATOR_REQUIRED",
                "message": "Diperlukan tindakan operator: unggah dokumen lartas",
                "requiredDocuments": ["SNI certificate", "BPOM approval"],
            })

    elif scenario == "PENDING_LONG":
        if poll_count >= 4:
            return JSONResponse({
                "ajuNumber": aju_number,
                "status": "ACCEPTED",
                "ceiSaReference": f"PIB-{aju_number}-LONG",
                "message": "PIB berhasil setelah proses pemeriksaan panjang",
                "acceptedAt": datetime.now(timezone.utc).isoformat(),
            })

    # Still processing
    return JSONResponse({
        "ajuNumber": aju_number,
        "status": "PROCESSING",
        "message": "Dokumen sedang dalam proses pemeriksaan",
        "pollCount": poll_count,
        "estimatedCompletion": "30 detik",
    })


@app.get("/health")
async def health() -> JSONResponse:
    return JSONResponse({
        "status": "ok",
        "service": "ceisa-simulator",
        "active_submissions": len(_submissions),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })


@app.post("/admin/reset")
async def reset_state() -> JSONResponse:
    """Reset all simulation state (dev/test use only)."""
    _submissions.clear()
    _poll_counts.clear()
    _timeout_counts.clear()
    return JSONResponse({"status": "reset", "message": "All simulation state cleared"})


@app.get("/admin/submissions")
async def list_submissions() -> JSONResponse:
    """List all tracked submissions for debugging."""
    return JSONResponse({
        "count": len(_submissions),
        "submissions": [
            {
                "ajuNumber": aju,
                "scenario": s["scenario"],
                "status": s["status"],
                "pollCount": s["pollCount"],
                "nomorBl": s["nomorBl"],
            }
            for aju, s in _submissions.items()
        ],
    })


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8006)
