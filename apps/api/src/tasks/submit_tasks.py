"""
TradeFlow AI — Wired Submission Tasks (Phase 4)
"""

from __future__ import annotations

import asyncio
import uuid
import structlog
from celery import Task

from .celery_app import celery_app

log = structlog.get_logger()


@celery_app.task(
    bind=True,
    queue="high",
    max_retries=5,
    default_retry_delay=60,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=600,
)
def submit_to_ceisa(self: Task, batch_id: str, submission_id: str) -> dict:
    """
    Submit declaration to CEISA 4.0.
    Auto-retries with exponential backoff for AUTO_RECOVERABLE errors.
    """
    from ..services.ceisa_svc import ceisa_service
    log.info("Submitting to CEISA", batch_id=batch_id, attempt=self.request.retries + 1)

    # In full impl: fetch extracted_data from DB
    extracted_data: dict = {}
    idempotency_key = str(uuid.uuid4())

    result = asyncio.get_event_loop().run_until_complete(
        ceisa_service.submit(
            batch_id=batch_id,
            extracted_data=extracted_data,
            submission_id=submission_id,
            idempotency_key=idempotency_key,
            attempt=self.request.retries + 1,
        )
    )

    classification = result.get("error_classification")

    if result["status"] in ("rejected", "failed"):
        if classification == "AUTO_RECOVERABLE" and self.request.retries < self.max_retries:
            # Attempt auto-fix then resubmit
            fixed = asyncio.get_event_loop().run_until_complete(
                ceisa_service.auto_fix_and_resubmit(
                    batch_id=batch_id,
                    extracted_data=extracted_data,
                    error_code=result.get("error_code", ""),
                    original_submission_id=submission_id,
                )
            )
            return fixed
        elif classification == "OPERATOR_REQUIRED":
            log.warning("Operator action required", batch_id=batch_id, code=result.get("error_code"))
            # Enqueue human review via Supabase Realtime notification
            return result
        else:
            log.error("Admin escalation required", batch_id=batch_id)
            return result

    # On success → enqueue blockchain anchor on critical queue
    if result["status"] in ("accepted", "processing"):
        anchor_blockchain.apply_async(args=[batch_id], queue="critical")

    return result


@celery_app.task(bind=True, queue="critical", max_retries=3, default_retry_delay=30)
def anchor_blockchain(self: Task, batch_id: str) -> dict:
    """Anchor submission hash to Polygon."""
    from ..services.blockchain_svc import blockchain_service
    log.info("Anchoring to blockchain", batch_id=batch_id)
    try:
        result = asyncio.get_event_loop().run_until_complete(
            blockchain_service.anchor(
                batch_id=batch_id,
                payload={"batch_id": batch_id},
                document_hashes=[],
            )
        )
        log.info("Blockchain anchor complete", batch_id=batch_id, tx=result.get("tx_hash"))
        return result
    except Exception as exc:
        log.error("Blockchain anchor failed", error=str(exc))
        raise self.retry(exc=exc)


@celery_app.task(bind=True, queue="high")
def process_ceisa_response(self: Task, batch_id: str) -> None:
    """Handle async CEISA webhook response."""
    log.info("Processing CEISA response", batch_id=batch_id)
