from __future__ import annotations

import asyncio
import sys
from typing import Any
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from supabase import acreate_client

from src.ai.nodes.risk import risk_assessment_node
from src.config import settings


def _coerce_field(field: str, value: Any) -> Any:
    if value is None:
        return None
    if field in {"gross_weight", "cif_value", "fob_value"}:
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


async def backfill_batch_risk(batch_id: str) -> dict[str, Any]:
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
    validations = (
        await supabase.table("validation_results").select("*").eq("batch_id", batch_id).execute()
    ).data or []

    combined: dict[str, Any] = {}
    confidences: dict[str, float] = {}
    for row in fields:
        name = row.get("ceisa_field")
        if not name:
            continue
        combined[name] = _coerce_field(
            name,
            row.get("normalized_value") or row.get("extracted_value"),
        )
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
                "extracted_data": {},
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
        "validation_results": validations,
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

    result = await risk_assessment_node(state)  # type: ignore[arg-type]
    payload = {
        "risk_level": result.get("risk_level"),
        "customs_readiness_score": result.get("customs_readiness_score"),
        "crs_grade": result.get("crs_grade"),
        "rejection_probability": result.get("rejection_probability"),
    }
    await supabase.table("batches").update(payload).eq("id", batch_id).execute()
    return payload


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python /app/src/scripts/backfill_batch_risk.py <batch_id>")
    print(asyncio.run(backfill_batch_risk(sys.argv[1])))
