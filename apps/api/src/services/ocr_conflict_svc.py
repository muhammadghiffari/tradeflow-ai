"""
OCR ensemble reconciliation for CIPL documents.

The service accepts candidate field maps from multiple engines (PaddleOCR,
Azure DI, direct PDF text, or LLM extraction) and produces one CEISA-ready
field map with per-field confidence and explicit conflict flags.
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

import structlog

log = structlog.get_logger()


DEFAULT_ENGINE_WEIGHTS = {
    "pdf_text": 1.00,
    "azure-di": 0.92,
    "azure-di-fallback": 0.90,
    "paddleocr": 0.84,
    "gemini": 0.82,
    "rule_based": 0.70,
}

NUMERIC_FIELDS = {"total_packages", "gross_weight", "cif_value"}


@dataclass(frozen=True)
class FieldCandidate:
    field: str
    value: Any
    confidence: float
    engine: str


def _normalize_value(field: str, value: Any) -> str:
    if value is None:
        return ""

    text = str(value).strip()
    if not text:
        return ""

    if field in NUMERIC_FIELDS:
        cleaned = re.sub(r"[^0-9.,-]", "", text).replace(",", "")
        try:
            number = Decimal(cleaned)
            return str(number.normalize())
        except (InvalidOperation, ValueError):
            return cleaned.lower()

    if field == "importer_npwp":
        return re.sub(r"\D", "", text)

    if field == "currency":
        return text.upper()[:3]

    return re.sub(r"\s+", " ", text).casefold()


def _candidate_from_mapping(engine: str, mapping: dict[str, Any]) -> list[FieldCandidate]:
    confidence = float(mapping.get("confidence", mapping.get("overall_confidence", 0.75)))
    data = mapping.get("fields", mapping)
    candidates = []
    for field, value in data.items():
        if field in {"confidence", "overall_confidence", "field_confidences"}:
            continue
        field_confidences = mapping.get("field_confidences", {})
        field_confidence = float(field_confidences.get(field, confidence))
        candidates.append(FieldCandidate(field, value, max(0.0, min(1.0, field_confidence)), engine))
    return candidates


def reconcile_ocr_candidates(
    candidates_by_engine: dict[str, dict[str, Any]],
    *,
    engine_weights: dict[str, float] | None = None,
    conflict_margin: float = 0.12,
    min_auto_confidence: float = 0.70,
) -> dict[str, Any]:
    """Return reconciled fields, per-field confidence, and conflict evidence."""
    weights = {**DEFAULT_ENGINE_WEIGHTS, **(engine_weights or {})}
    grouped: dict[str, list[FieldCandidate]] = defaultdict(list)

    for engine, mapping in candidates_by_engine.items():
        for candidate in _candidate_from_mapping(engine, mapping or {}):
            if _normalize_value(candidate.field, candidate.value):
                grouped[candidate.field].append(candidate)

    fields: dict[str, Any] = {}
    field_confidences: dict[str, float] = {}
    conflicts: list[dict[str, Any]] = []

    for field, candidates in grouped.items():
        scored_values: dict[str, dict[str, Any]] = {}
        for candidate in candidates:
            normalized = _normalize_value(field, candidate.value)
            weighted_score = candidate.confidence * weights.get(candidate.engine, 0.75)
            bucket = scored_values.setdefault(
                normalized,
                {"score": 0.0, "support": [], "display_value": candidate.value},
            )
            bucket["score"] += weighted_score
            bucket["support"].append(
                {
                    "engine": candidate.engine,
                    "confidence": candidate.confidence,
                    "value": candidate.value,
                }
            )

        ranked = sorted(scored_values.values(), key=lambda item: item["score"], reverse=True)
        winner = ranked[0]
        runner_up = ranked[1] if len(ranked) > 1 else None
        total_score = sum(item["score"] for item in ranked) or 1.0
        consensus_confidence = min(0.99, winner["score"] / total_score)

        fields[field] = winner["display_value"]
        field_confidences[field] = round(consensus_confidence, 4)

        has_close_conflict = runner_up and (winner["score"] - runner_up["score"]) < conflict_margin
        if has_close_conflict or consensus_confidence < min_auto_confidence:
            conflicts.append(
                {
                    "field": field,
                    "selected_value": winner["display_value"],
                    "confidence": round(consensus_confidence, 4),
                    "candidates": ranked,
                    "reason": "engine_disagreement" if runner_up else "low_confidence",
                }
            )

    needs_review = any(item["confidence"] < min_auto_confidence for item in conflicts)
    if conflicts:
        log.info("OCR conflicts detected", conflict_count=len(conflicts))

    return {
        "fields": fields,
        "field_confidences": field_confidences,
        "conflicts": conflicts,
        "needs_human_review": needs_review,
    }
