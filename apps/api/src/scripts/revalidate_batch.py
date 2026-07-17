from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from supabase import acreate_client

from src.ai.nodes.risk import risk_assessment_node
from src.config import settings
from src.services.validation_rules_svc import validation_rules_service


def _coerce_field(field: str, value: Any) -> Any:
    if value is None:
        return None
    if field in {"gross_weight", "cif_value", "fob_value", "freight_value", "insurance_value"}:
        try:
            return float(str(value).replace(",", ""))
        except Exception:
            return value
    if field == "total_packages":
        try:
            return int(float(str(value).replace(",", "")))
        except Exception:
            return value
    return value


async def revalidate_batch(batch_id: str) -> dict[str, Any]:
    supabase = await acreate_client(
        settings.SUPABASE_URL,
        settings.SUPABASE_SERVICE_KEY.get_secret_value(),
    )
    docs = (
        await supabase.table("documents").select("*").eq("batch_id", batch_id).execute()
    ).data or []
    fields = (
        await supabase.table("extracted_fields").select("*").eq("batch_id", batch_id).execute()
    ).data or []

    by_doc: dict[str, dict[str, Any]] = {}
    combined: dict[str, Any] = {}
    confidences: dict[str, float] = {}
    for row in fields:
        document_id = row.get("document_id")
        name = row.get("ceisa_field")
        if not document_id or not name:
            continue
        value = _coerce_field(name, row.get("normalized_value") or row.get("extracted_value"))
        by_doc.setdefault(document_id, {})[name] = value
        combined[name] = value
        confidences[name] = float(row.get("confidence") or 0.0)

    state = {
        "batch_id": batch_id,
        "company_id": "",
        "documents": [
            {
                "doc_id": doc["id"],
                "doc_type": doc.get("doc_type"),
                "storage_path": doc.get("storage_path"),
                "pages": [],
                "extracted_data": by_doc.get(doc["id"], {}),
                "quality_score": float(doc.get("quality_score") or 1.0),
                "ocr_method": doc.get("ocr_engine_used"),
                "error": doc.get("error_message"),
                "ocr_candidates": {},
                "ocr_conflicts": [],
                "field_confidences": {},
            }
            for doc in docs
        ],
        "combined_data": combined,
        "validation_results": [],
        "needs_human_review": False,
        "risk_level": "UNKNOWN",
        "customs_readiness_score": None,
        "crs_grade": None,
        "rejection_probability": None,
        "risk_features": {},
        "ocr_conflicts": [],
        "field_confidences": confidences,
        "steps": [],
    }

    validations, needs_review = validation_rules_service.evaluate(state)
    state["validation_results"] = validations
    state["needs_human_review"] = needs_review
    risk = await risk_assessment_node(state)  # type: ignore[arg-type]

    await supabase.table("validation_results").delete().eq("batch_id", batch_id).execute()
    if validations:
        await supabase.table("validation_results").insert([
            {
                "batch_id": batch_id,
                "rule_id": row.get("rule_id", "UNKNOWN"),
                "rule_name": row.get("rule_name", row.get("message", "Validation")),
                "severity": row.get("severity", "WARNING"),
                "error_message": row.get("message"),
                "affected_fields": row.get("affected_fields", []),
            }
            for row in validations
        ]).execute()

    payload = {
        "status": "review_ready" if risk.get("needs_human_review") else "validated",
        "risk_level": risk.get("risk_level"),
        "customs_readiness_score": risk.get("customs_readiness_score"),
        "crs_grade": risk.get("crs_grade"),
        "rejection_probability": risk.get("rejection_probability"),
    }
    await supabase.table("batches").update(payload).eq("id", batch_id).execute()
    return {
        **payload,
        "validation_counts": {
            severity: sum(1 for row in validations if row.get("severity") == severity)
            for severity in {"PASS", "WARNING", "CRITICAL_FAIL"}
        },
    }


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python /app/src/scripts/revalidate_batch.py <batch_id>")
    print(asyncio.run(revalidate_batch(sys.argv[1])))
