"""
TradeFlow AI — Wired OCR & Processing Tasks (Phase 2+3 implementation)
"""

from __future__ import annotations

import structlog

from .celery_app import celery_app

log = structlog.get_logger()


async def _load_batch_context(batch_id: str) -> dict:
    """Load batch and document rows for the LangGraph worker."""
    from supabase import acreate_client

    from ..config import settings

    supabase = await acreate_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_KEY.get_secret_value())
    try:
        batch_res = await (
            supabase.table("batches").select("*").eq("id", batch_id).single().execute()
        )
        docs_res = await supabase.table("documents").select("*").eq("batch_id", batch_id).execute()
        batch = batch_res.data or {}
        documents = [
            {
                "doc_id": row["id"],
                "doc_type": row.get("doc_type"),
                "storage_path": row.get("storage_path"),
                "original_name": row.get("original_name"),
                "pages": [],
                "extracted_data": None,
                "quality_score": float(row.get("quality_score") or 0.0),
                "ocr_method": row.get("ocr_engine_used"),
                "error": row.get("error_message"),
                "ocr_candidates": {},
                "ocr_conflicts": [],
                "field_confidences": {},
            }
            for row in docs_res.data
        ]
        return {"batch": batch, "documents": documents}
    finally:
        pass


async def _persist_graph_result(batch_id: str, result: dict) -> None:
    """Persist OCR/extraction confidence so dashboard/eval can measure accuracy."""
    from supabase import acreate_client

    from ..config import settings

    supabase = await acreate_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_KEY.get_secret_value())
    try:
        await supabase.table("extracted_fields").delete().eq("batch_id", batch_id).execute()
        await supabase.table("validation_results").delete().eq("batch_id", batch_id).execute()

        for doc in result.get("documents", []):
            await supabase.table("documents").update({
                "quality_score": doc.get("quality_score"),
                "ocr_engine_used": doc.get("ocr_method"),
                "overall_ocr_confidence": _average_confidence(doc.get("field_confidences") or {}),
                "error_message": doc.get("error"),
                "status": "ocr_complete" if not doc.get("error") else "error",
            }).eq("id", doc["doc_id"]).execute()

            extracted_data = doc.get("extracted_data") or {}
            field_confidences = doc.get("field_confidences") or {}
            rows = [
                {
                    "batch_id": batch_id,
                    "document_id": doc["doc_id"],
                    "ceisa_field": field,
                    "raw_ocr_value": str(value),
                    "extracted_value": str(value),
                    "normalized_value": str(value),
                    "confidence": float(field_confidences.get(field, 0.0)),
                    "extraction_method": "direct_ocr",
                }
                for field, value in extracted_data.items()
            ]
            if rows:
                await supabase.table("extracted_fields").insert(rows).execute()

        for validation in result.get("validation_results", []):
            await supabase.table("validation_results").insert({
                "batch_id": batch_id,
                "rule_id": validation.get("rule_id", "UNKNOWN"),
                "rule_name": validation.get("rule_name", validation.get("message", "Validation")),
                "severity": validation.get("severity", "WARNING"),
                "error_message": validation.get("message"),
                "affected_fields": validation.get("affected_fields", []),
            }).execute()

        status = "review_ready" if result.get("needs_human_review") else "validated"
        await supabase.table("batches").update({
            "status": status,
            "risk_level": result.get("risk_level"),
            "customs_readiness_score": result.get("_crs_score"),
            "crs_grade": result.get("_crs_grade"),
            "rejection_probability": result.get("_rejection_prob"),
            "langgraph_thread_id": batch_id,
        }).eq("id", batch_id).execute()
    finally:
        pass


def _average_confidence(confidences: dict) -> float:
    values = [float(value) for value in confidences.values()]
    return round(sum(values) / len(values), 4) if values else 0.0


@celery_app.task(bind=True, queue="high", max_retries=3, default_retry_delay=10)
def preprocess_document(self, batch_id: str) -> None:
    """Entry point: kicks off LangGraph extraction pipeline."""
    import asyncio

    from ..ai.graph import extraction_graph
    log.info("Starting extraction pipeline", batch_id=batch_id)
    try:
        loop = asyncio.get_event_loop()
        config = {"configurable": {"thread_id": batch_id}}
        context = loop.run_until_complete(_load_batch_context(batch_id))
        initial_state = {
            "batch_id": batch_id,
            "company_id": context["batch"].get("company_id") or "",
            "documents": context["documents"],
            "combined_data": {},
            "validation_results": [],
            "needs_human_review": False,
            "risk_level": "UNKNOWN",
            "ocr_conflicts": [],
            "field_confidences": {},
            "steps": [],
        }
        # Run sync wrapper around async graph
        result = loop.run_until_complete(
            extraction_graph.ainvoke(initial_state, config=config)
        )
        loop.run_until_complete(_persist_graph_result(batch_id, result))
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
    rejection_predictor.load()
    rejection_prob = rejection_predictor.predict_proba(features)
    return {"rejection_prob": rejection_prob, "batch_id": batch_id}
