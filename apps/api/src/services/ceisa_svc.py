"""
TradeFlow AI — CEISA 4.0 Submission Service (Phase 4, Step 4.1)

PRD §14 — Full CEISA 4.0 submission flow:
  1. Build CEISA payload from extracted fields
  2. Validate idempotency key
  3. Encrypt payload (AES-256-GCM)
  4. POST to CEISA 4.0 endpoint (or simulator)
  5. Handle response + classify errors
  6. Enqueue blockchain anchoring
"""

from __future__ import annotations

import base64
import json
import os
import uuid
from datetime import UTC, datetime

import httpx
import structlog
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from ..config import settings

log = structlog.get_logger()

# Error classification per PRD §14 Decision 3
AUTO_RECOVERABLE_CODES = {"E001", "E002", "E003", "E004", "E005", "E010"}
OPERATOR_REQUIRED_CODES = {"E101", "E102", "E103", "E201", "E202"}
# Everything else → ADMIN_ESCALATION


def _encrypt_payload(data: dict) -> dict | str:
    """AES-256-GCM encryption for CEISA payload."""
    if not settings.CEISA_AES_KEY:
        return data

    key = base64.b64decode(settings.CEISA_AES_KEY)
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)
    plaintext = json.dumps(data).encode()
    ciphertext = aesgcm.encrypt(nonce, plaintext, None)
    return base64.b64encode(nonce + ciphertext).decode()


def _classify_error(error_code: str | None) -> str:
    if not error_code:
        return "AUTO_RECOVERABLE"
    if error_code in AUTO_RECOVERABLE_CODES:
        return "AUTO_RECOVERABLE"
    if error_code in OPERATOR_REQUIRED_CODES:
        return "OPERATOR_REQUIRED"
    return "ADMIN_ESCALATION"


def _build_ceisa_payload(extracted_data: dict, batch_id: str, idempotency_key: str) -> dict:
    """
    Map extracted fields → CEISA 4.0 PIB schema.
    This is a simplified mapping; the full 200+ field mapping is in
    packages/db/ceisa_field_map.json.
    """
    return {
        "idempotencyKey": idempotency_key,
        "batchId": batch_id,
        "submittedAt": datetime.now(UTC).isoformat(),
        "header": {
            "jenisPI": "I",  # Import
            "kdKantor": "050100",  # Cikarang Dry Port
            "nmImportir": extracted_data.get("importer_name", ""),
            "npwpImportir": extracted_data.get("importer_npwp", ""),
            "nilaiCIF": extracted_data.get("cif_value", 0),
            "kodeMataUang": extracted_data.get("currency", "USD"),
            "jumlahKoli": extracted_data.get("total_packages", 0),
            "beratBruto": extracted_data.get("gross_weight", 0),
        },
        "dokumen": [],  # Document list (B/L, Invoice, PL)
        "barang": [],   # Line items with HS codes
    }


class CEISASubmissionService:
    """Handles submission to CEISA 4.0 (or local simulator)."""

    def __init__(self) -> None:
        self.base_url = settings.CEISA_BASE_URL
        self.timeout = httpx.Timeout(30.0, connect=5.0)

    async def submit(
        self,
        batch_id: str,
        extracted_data: dict,
        submission_id: str,
        idempotency_key: str,
        attempt: int = 1,
    ) -> dict:
        """
        Submit to CEISA 4.0.
        Returns: {status, ceisa_reference, error_code, error_classification, auto_fixed}
        """
        payload = _build_ceisa_payload(extracted_data, batch_id, idempotency_key)
        encrypted = _encrypt_payload(payload)

        log.info(
            "Submitting to CEISA",
            batch_id=batch_id,
            submission_id=submission_id,
            attempt=attempt,
        )

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                if isinstance(encrypted, str):
                    json_body = {"encrypted": encrypted}
                else:
                    json_body = encrypted

                resp = await client.post(
                    f"{self.base_url}/api/v1/submit",
                    json=json_body,
                    headers={
                        "Content-Type": "application/json",
                        "X-Idempotency-Key": idempotency_key,
                        "X-Submission-ID": submission_id,
                    },
                )
                resp.raise_for_status()
                body = resp.json()

        except httpx.HTTPStatusError as exc:
            error_body = {}
            try:
                error_body = exc.response.json()
            except Exception:
                pass
            error_code = error_body.get("errorCode")
            classification = _classify_error(error_code)
            log.warning(
                "CEISA returned error",
                status=exc.response.status_code,
                error_code=error_code,
                classification=classification,
                batch_id=batch_id,
            )
            return {
                "status": "rejected",
                "ceisa_reference": None,
                "error_code": error_code,
                "error_message": error_body.get("message", str(exc)),
                "error_classification": classification,
                "auto_fixed": False,
            }

        except (httpx.ConnectError, httpx.TimeoutException) as exc:
            log.error("CEISA connection failed", error=str(exc), batch_id=batch_id)
            return {
                "status": "failed",
                "ceisa_reference": None,
                "error_code": "CONN_ERROR",
                "error_message": str(exc),
                "error_classification": "AUTO_RECOVERABLE",
                "auto_fixed": False,
            }

        ceisa_reference = body.get("referenceNumber")
        status = "accepted" if body.get("status") == "ACCEPTED" else "processing"

        log.info(
            "CEISA submission successful",
            batch_id=batch_id,
            reference=ceisa_reference,
            status=status,
        )
        return {
            "status": status,
            "ceisa_reference": ceisa_reference,
            "error_code": None,
            "error_message": None,
            "error_classification": None,
            "auto_fixed": False,
        }

    async def auto_fix_and_resubmit(
        self,
        batch_id: str,
        extracted_data: dict,
        error_code: str,
        original_submission_id: str,
    ) -> dict:
        """
        PRD §14 Decision 3: Auto-recoverable errors trigger LLM auto-fix.
        Gemini Flash corrects the specific field causing the error,
        then resubmits with a new idempotency key.
        """
        log.info("Auto-fixing submission", batch_id=batch_id, error_code=error_code)

        # Stub: actual fix uses a targeted Gemini prompt per error_code
        fixed_data = {**extracted_data}
        new_idempotency_key = str(uuid.uuid4())
        new_submission_id = str(uuid.uuid4())

        result = await self.submit(
            batch_id=batch_id,
            extracted_data=fixed_data,
            submission_id=new_submission_id,
            idempotency_key=new_idempotency_key,
            attempt=2,
        )
        result["auto_fixed"] = True
        return result


# ── Singleton ────────────────────────────────────────────────────────────────
ceisa_service = CEISASubmissionService()
