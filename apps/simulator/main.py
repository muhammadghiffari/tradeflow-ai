"""
TradeFlow AI — CEISA 4.0 Simulator

Simulates the CEISA 4.0 customs submission API for local development
and end-to-end testing without real DJBC connectivity.

PRD §7 — Dedicated simulator service exposing:
  POST /api/v1/submit        → Accept/Reject with configurable rates
  GET  /api/v1/status/{ref}  → Poll submission status
  POST /admin/scenario        → Set test scenario (always_accept, always_reject, flaky)
  GET  /health               → Health check
"""

from __future__ import annotations

import hashlib
import random
import time
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel

app = FastAPI(
    title="CEISA 4.0 Simulator",
    description="Local simulator for DJBC CEISA 4.0 customs submission API",
    version="1.0.0",
)

# ── In-memory store ───────────────────────────────────────────────────────────
submissions: dict[str, dict] = {}
current_scenario = "realistic"  # "always_accept" | "always_reject" | "flaky" | "realistic"

# CEISA error codes + descriptions (realistic)
REALISTIC_ERRORS = [
    ("E101", "Nilai CIF tidak sesuai dengan dokumen pendukung"),
    ("E102", "Kode HS tidak ditemukan dalam BTKI"),
    ("E201", "NPWP importir tidak valid"),
    ("E001", "Format tanggal tidak valid — dapat diperbaiki otomatis"),
    ("E003", "Kode satuan tidak standar — dapat diperbaiki otomatis"),
]


class SubmitResponse(BaseModel):
    status: str
    referenceNumber: str | None = None
    message: str
    errorCode: str | None = None
    timestamp: str


class ScenarioRequest(BaseModel):
    scenario: str  # "always_accept" | "always_reject" | "flaky" | "realistic"
    reject_rate: float = 0.15  # Only used in "realistic" mode


scenario_config = {"reject_rate": 0.15}


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "ceisa-simulator", "scenario": current_scenario}


@app.post("/api/v1/submit")
async def submit(request: Request) -> SubmitResponse:
    global current_scenario

    idempotency_key = request.headers.get("X-Idempotency-Key", str(uuid.uuid4()))
    submission_id   = request.headers.get("X-Submission-ID", str(uuid.uuid4()))

    # Idempotency — return same result if already processed
    if idempotency_key in submissions:
        stored = submissions[idempotency_key]
        return SubmitResponse(**stored)

    timestamp = datetime.now(timezone.utc).isoformat()

    # ── Scenario logic ─────────────────────────────────────────────
    if current_scenario == "always_accept":
        result = _make_accept(timestamp)
    elif current_scenario == "always_reject":
        result = _make_reject(timestamp)
    elif current_scenario == "flaky":
        # Simulate intermittent failures (network timeouts, server errors)
        roll = random.random()
        if roll < 0.3:
            raise HTTPException(status_code=503, detail="Service temporarily unavailable")
        elif roll < 0.5:
            result = _make_reject(timestamp)
        else:
            result = _make_accept(timestamp)
    else:  # realistic
        if random.random() < scenario_config["reject_rate"]:
            result = _make_reject(timestamp)
        else:
            result = _make_accept(timestamp)

    # Store for idempotency
    submissions[idempotency_key] = result
    return SubmitResponse(**result)


@app.get("/api/v1/status/{reference_number}")
async def get_status(reference_number: str) -> dict[str, Any]:
    # Find submission by reference number
    for data in submissions.values():
        if data.get("referenceNumber") == reference_number:
            return {
                "referenceNumber": reference_number,
                "status": data.get("status"),
                "updatedAt": datetime.now(timezone.utc).isoformat(),
            }
    raise HTTPException(status_code=404, detail=f"Reference {reference_number} not found")


@app.post("/admin/scenario")
async def set_scenario(request: ScenarioRequest) -> dict[str, str]:
    global current_scenario
    valid = {"always_accept", "always_reject", "flaky", "realistic"}
    if request.scenario not in valid:
        raise HTTPException(status_code=400, detail=f"Invalid scenario. Must be one of: {valid}")
    current_scenario = request.scenario
    scenario_config["reject_rate"] = request.reject_rate
    return {"scenario": current_scenario, "reject_rate": str(request.reject_rate)}


@app.delete("/admin/reset")
async def reset() -> dict[str, int]:
    submissions.clear()
    return {"cleared": 0}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_accept(timestamp: str) -> dict:
    ref = f"PIB-{hashlib.sha256(str(time.time_ns()).encode()).hexdigest()[:10].upper()}"
    return {
        "status": "ACCEPTED",
        "referenceNumber": ref,
        "message": "Permohonan pabean diterima oleh sistem CEISA 4.0",
        "errorCode": None,
        "timestamp": timestamp,
    }


def _make_reject(timestamp: str) -> dict:
    code, msg = random.choice(REALISTIC_ERRORS)
    return {
        "status": "REJECTED",
        "referenceNumber": None,
        "message": msg,
        "errorCode": code,
        "timestamp": timestamp,
    }
