"""
TradeFlow AI — Fallback OCR Node (Step 2.3)

Used when Gemini extraction fails or confidence is too low.
"""

import re

import structlog

from ...config import settings
from ...services.ocr_conflict_svc import reconcile_ocr_candidates
from ..state import ExtractionGraphState

log = structlog.get_logger()


def _needs_reconciliation(doc: dict) -> bool:
    confidences = doc.get("field_confidences") or {}
    return (
        bool(doc.get("error"))
        or not doc.get("extracted_data")
        or doc.get("quality_score", 1.0) < settings.OCR_FALLBACK_TRIGGER_QUALITY
        or bool(doc.get("ocr_conflicts"))
        or (
            len(doc.get("ocr_candidates") or {}) > 1
            and doc.get("document_mode") != "digital_pdf_text"
        )
        or bool(
            confidences
            and min(confidences.values()) < settings.OCR_FALLBACK_TRIGGER_CONFIDENCE
        )
    )


def _rule_based_candidates(doc: dict) -> dict:
    """Extract obvious CEISA fields from embedded text without external OCR."""
    text = "\n".join(str(page) for page in doc.get("pages", []) if isinstance(page, str))
    text = "\n".join([doc.get("raw_text", ""), doc.get("text_layer", ""), text])

    fields = {}
    npwp = re.search(r"\b(?:NPWP|Tax\s*ID)\D*([0-9.\- ]{10,24})", text, re.IGNORECASE)
    packages = re.search(r"\b(?:total\s+packages|packages|koli)\D*(\d{1,7})", text, re.IGNORECASE)
    gross = re.search(r"\b(?:gross\s+weight|gross)\D*([0-9,.]+)", text, re.IGNORECASE)
    cif = re.search(
        r"\b(?:CIF|total\s+amount|invoice\s+value)\D*([A-Z]{3})?\s*([0-9,.]+)",
        text,
        re.IGNORECASE,
    )

    if npwp:
        fields["importer_npwp"] = npwp.group(1)
    if packages:
        fields["total_packages"] = int(packages.group(1))
    if gross:
        fields["gross_weight"] = float(gross.group(1).replace(",", ""))
    if cif:
        if cif.group(1):
            fields["currency"] = cif.group(1).upper()
        fields["cif_value"] = float(cif.group(2).replace(",", ""))

    return {"fields": fields, "confidence": 0.68}


async def fallback_ocr_node(state: ExtractionGraphState) -> dict:
    """
    Step 2.3: Fallback OCR using Azure Document Intelligence or PaddleOCR.
    """
    log.info("Running fallback_ocr_node", batch_id=state["batch_id"])

    updated_docs = []
    all_conflicts = list(state.get("ocr_conflicts", []))
    combined_data = dict(state.get("combined_data", {}))
    needs_review = state.get("needs_human_review", False)
    field_confidences = dict(state.get("field_confidences", {}))

    for doc in state["documents"]:
        if _needs_reconciliation(doc):
            log.info("Reconciling fallback OCR candidates for doc", doc_id=doc["doc_id"])
            candidates = dict(doc.get("ocr_candidates") or {})

            if doc.get("extracted_data"):
                candidates[doc.get("ocr_method") or "gemini"] = {
                    "fields": doc["extracted_data"],
                    "confidence": 0.82,
            }
            if settings.ENABLE_DUAL_OCR and "azure-di" not in candidates:
                log.warning(
                    "Azure DI candidate missing; preserving degraded OCR evidence",
                    doc_id=doc["doc_id"],
                )
            rule_candidate = _rule_based_candidates(doc)
            if rule_candidate["fields"]:
                candidates["rule_based"] = rule_candidate

            reconciled = reconcile_ocr_candidates(candidates)
            doc["ocr_method"] = "ensemble-reconciled"
            doc["extracted_data"] = reconciled["fields"]
            doc["field_confidences"] = reconciled["field_confidences"]
            doc["ocr_conflicts"] = reconciled["conflicts"]
            doc["error"] = None if reconciled["fields"] else "No OCR engine produced usable fields"

            combined_data.update(reconciled["fields"])
            field_confidences.update(reconciled["field_confidences"])
            all_conflicts.extend(
                {**conflict, "doc_id": doc["doc_id"]} for conflict in reconciled["conflicts"]
            )
            needs_review = needs_review or reconciled["needs_human_review"] or bool(doc["error"])

        updated_docs.append(doc)

    return {
        "documents": updated_docs,
        "combined_data": combined_data,
        "field_confidences": field_confidences,
        "ocr_conflicts": all_conflicts,
        "needs_human_review": needs_review,
        "steps": ["fallback_ocr"]
    }
