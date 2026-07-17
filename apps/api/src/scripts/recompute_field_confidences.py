from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from supabase import acreate_client

from src.ai.nodes.extract import _estimate_field_confidences
from src.config import settings
from src.services.ingest_svc import get_storage_service
from src.services.ocr_engine_svc import ocr_engine_service


async def recompute_field_confidences(batch_id: str) -> dict[str, Any]:
    supabase = await acreate_client(
        settings.SUPABASE_URL,
        settings.SUPABASE_SERVICE_KEY.get_secret_value(),
    )

    docs = (
        await supabase.table("documents").select("*").eq("batch_id", batch_id).execute()
    ).data or []
    rows = (
        await supabase.table("extracted_fields").select("*").eq("batch_id", batch_id).execute()
    ).data or []

    fields_by_doc: dict[str, dict[str, Any]] = {}
    row_keys_by_doc_field: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in rows:
        document_id = row.get("document_id")
        field = row.get("ceisa_field")
        if not document_id or not field:
            continue
        fields_by_doc.setdefault(document_id, {})[field] = row.get("normalized_value") or row.get("extracted_value")
        row_keys_by_doc_field.setdefault((document_id, field), []).append(row)

    storage = get_storage_service()
    updated = 0
    doc_summaries = []

    for doc in docs:
        doc_id = doc["id"]
        extracted = fields_by_doc.get(doc_id) or {}
        if not extracted:
            continue

        raw_text = ""
        direct_candidate: dict[str, Any] = {}
        try:
            file_bytes = await storage.download_document(doc["storage_path"])
            filename = doc.get("original_name") or doc.get("storage_path") or ""
            if str(filename).lower().endswith(".pdf"):
                direct_candidate = ocr_engine_service._extract_pdf_text(file_bytes)
                raw_text = direct_candidate.get("text") or ""
        except Exception as exc:
            print(f"warning: failed to reload {doc.get('original_name')}: {exc}")

        doc_state = {
            "document_mode": "digital_pdf_text" if raw_text else doc.get("processing_route"),
            "raw_text": raw_text,
            "ocr_candidates": {"pdf_text": direct_candidate} if direct_candidate else {},
        }
        confidences = _estimate_field_confidences(extracted, doc_state)
        if not confidences:
            continue

        for field, confidence in confidences.items():
            for row in row_keys_by_doc_field.get((doc_id, field), []):
                row_id = row.get("id")
                if row_id:
                    await supabase.table("extracted_fields").update({"confidence": confidence}).eq("id", row_id).execute()
                else:
                    await (
                        supabase.table("extracted_fields")
                        .update({"confidence": confidence})
                        .eq("batch_id", batch_id)
                        .eq("document_id", doc_id)
                        .eq("ceisa_field", field)
                        .execute()
                    )
                updated += 1

        avg_conf = round(sum(confidences.values()) / len(confidences), 4)
        await (
            supabase.table("documents")
            .update({"overall_ocr_confidence": avg_conf})
            .eq("id", doc_id)
            .execute()
        )
        doc_summaries.append(
            {
                "doc_type": doc.get("doc_type"),
                "original_name": doc.get("original_name"),
                "avg_confidence": avg_conf,
                "fields": len(confidences),
            }
        )

    return {"batch_id": batch_id, "updated_rows": updated, "documents": doc_summaries}


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python /app/src/scripts/recompute_field_confidences.py <batch_id>")
    print(asyncio.run(recompute_field_confidences(sys.argv[1])))
