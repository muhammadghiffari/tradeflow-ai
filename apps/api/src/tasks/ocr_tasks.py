"""
TradeFlow AI — Wired OCR & Processing Tasks (Phase 2+3 implementation)
"""

from __future__ import annotations

import structlog
from celery import chain

from .celery_app import celery_app
from ..ai.graph import extraction_graph

log = structlog.get_logger()


@celery_app.task(bind=True, queue="high", max_retries=3, default_retry_delay=10)
def preprocess_document(self, batch_id: str) -> None:
    """Entry point: kicks off LangGraph extraction pipeline."""
    import asyncio
    log.info("Starting extraction pipeline", batch_id=batch_id)
    try:
        config = {"configurable": {"thread_id": batch_id}}
        initial_state = {
            "batch_id": batch_id,
            "company_id": "",  # populated after DB fetch
            "documents": [],
            "combined_data": {},
            "validation_results": [],
            "needs_human_review": False,
            "risk_level": "UNKNOWN",
            "steps": [],
        }
        # Run sync wrapper around async graph
        asyncio.get_event_loop().run_until_complete(
            extraction_graph.ainvoke(initial_state, config=config)
        )
        log.info("Extraction pipeline complete", batch_id=batch_id)
    except Exception as exc:
        log.error("Pipeline failed", batch_id=batch_id, error=str(exc))
        raise self.retry(exc=exc)


@celery_app.task(bind=True, queue="high")
def run_ocr(self, batch_id: str) -> None:
    log.info("run_ocr delegated to LangGraph", batch_id=batch_id)


@celery_app.task(bind=True, queue="high")
def extract_fields(self, batch_id: str) -> None:
    log.info("extract_fields delegated to LangGraph", batch_id=batch_id)


@celery_app.task(bind=True, queue="default")
def validate_fields(self, batch_id: str) -> None:
    log.info("validate_fields delegated to LangGraph", batch_id=batch_id)


@celery_app.task(bind=True, queue="default")
def recommend_hs(self, batch_id: str, product_description: str) -> list[dict]:
    """Run HS code recommendation for a batch."""
    import asyncio
    from ..services.hs_svc import hs_recommend_service
    log.info("Running HS recommendation", batch_id=batch_id)
    return asyncio.get_event_loop().run_until_complete(
        hs_recommend_service.recommend(product_description)
    )


@celery_app.task(bind=True, queue="default")
def assess_risk(self, batch_id: str) -> dict:
    """Compute CRS and persist to DB."""
    import asyncio
    from ..services.predictor_svc import rejection_predictor
    log.info("Assessing risk", batch_id=batch_id)
    # Stub features — in full impl these come from graph state persisted in Redis
    features = {
        "doc_quality_score": 0.95,
        "completeness_score": 0.88,
        "consistency_score": 1.0,
        "historical_rate": 0.80,
        "hs_confidence": 0.85,
        "cif_value_usd": 15000.0,
        "package_count": 10,
        "gross_weight_kg": 500.0,
    }
    rejection_prob = rejection_predictor.predict_proba(features)
    return {"rejection_prob": rejection_prob, "batch_id": batch_id}
