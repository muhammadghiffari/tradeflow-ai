"""
TradeFlow AI — Risk Assessment Node (Step 2.5)

Runs the XGBoost rejection predictor and computes the
Customs Readiness Score (CRS) for a batch.

PRD §13 — CRS = weighted average across 5 pillars:
  (1) Document Quality 20%
  (2) Data Completeness 25%
  (3) Cross-document Consistency 30%
  (4) Historical Performance 15%
  (5) HS Code Confidence 10%
"""

from __future__ import annotations

import structlog

from ...services.predictor_svc import rejection_predictor
from ..state import ExtractionGraphState

log = structlog.get_logger()

# Pillar weights per PRD §13
PILLAR_WEIGHTS = {
    "doc_quality": 0.20,
    "completeness": 0.25,
    "consistency": 0.30,
    "historical": 0.15,
    "hs_confidence": 0.10,
}

REQUIRED_CEISA_FIELDS = [
    "importer_name", "importer_npwp", "total_packages",
    "gross_weight", "cif_value", "currency",
]


def _compute_completeness(combined_data: dict) -> float:
    filled = sum(1 for f in REQUIRED_CEISA_FIELDS if combined_data.get(f))
    return filled / len(REQUIRED_CEISA_FIELDS)


def _compute_consistency(validation_results: list[dict]) -> float:
    if not validation_results:
        return 1.0
    passed = sum(1 for r in validation_results if r.get("severity") == "PASS")
    return passed / len(validation_results)


def _compute_doc_quality(documents: list[dict]) -> float:
    scores = [d.get("quality_score", 0.8) for d in documents]
    return sum(scores) / len(scores) if scores else 0.0


def _crs_to_grade(score: float) -> str:
    if score >= 90:
        return "A"
    if score >= 80:
        return "B"
    if score >= 70:
        return "C"
    if score >= 60:
        return "D"
    return "F"


def _score_to_risk(score: float) -> str:
    if score >= 80:
        return "LOW"
    if score >= 65:
        return "MEDIUM"
    if score >= 50:
        return "HIGH"
    return "CRITICAL"


def _probability_to_risk(probability: float) -> str:
    if probability < 0.15:
        return "LOW"
    if probability < 0.35:
        return "MEDIUM"
    if probability < 0.60:
        return "HIGH"
    return "CRITICAL"


async def risk_assessment_node(state: ExtractionGraphState) -> dict:
    """
    Compute CRS (0-100) and rejection probability (0-1).

    XGBoost inference uses the shared predictor service, with heuristic
    fallback when no trained model is available yet.
    """
    log.info("Running risk_assessment_node", batch_id=state["batch_id"])

    combined_data = state.get("combined_data", {})
    validation_results = state.get("validation_results", [])
    documents = state.get("documents", [])

    # ── Pillar scores ──────────────────────────────────────────────
    p_quality     = _compute_doc_quality(documents)
    p_completeness = _compute_completeness(combined_data)
    p_consistency  = _compute_consistency(validation_results)
    p_historical   = 0.80  # Stub — fetched from company submission history
    p_hs_conf      = 0.85  # Stub — from HS recommender confidence

    # ── Weighted CRS ───────────────────────────────────────────────
    crs_raw = (
        p_quality      * PILLAR_WEIGHTS["doc_quality"]
        + p_completeness * PILLAR_WEIGHTS["completeness"]
        + p_consistency  * PILLAR_WEIGHTS["consistency"]
        + p_historical   * PILLAR_WEIGHTS["historical"]
        + p_hs_conf      * PILLAR_WEIGHTS["hs_confidence"]
    )
    crs_score = round(crs_raw * 100, 2)
    crs_grade = _crs_to_grade(crs_score)

    features = {
        "doc_quality_score": p_quality,
        "completeness_score": p_completeness,
        "consistency_score": p_consistency,
        "historical_rate": p_historical,
        "hs_confidence": p_hs_conf,
        "cif_value_usd": float(combined_data.get("cif_value") or 0.0),
        "package_count": float(combined_data.get("total_packages") or 0.0),
        "gross_weight_kg": float(combined_data.get("gross_weight") or 0.0),
    }
    rejection_prob = round(rejection_predictor.predict_proba(features), 4)
    risk_level = _probability_to_risk(rejection_prob)

    # PRD §13 Invariant: CRS < 70 → must NOT auto-submit
    needs_human_review = (
        state.get("needs_human_review", False)
        or crs_score < 70.0
        or rejection_prob >= 0.35
    )

    log.info(
        "CRS computed",
        batch_id=state["batch_id"],
        crs=crs_score,
        grade=crs_grade,
        risk=risk_level,
        rejection_prob=rejection_prob,
    )

    return {
        "risk_level": risk_level,
        "needs_human_review": needs_human_review,
        "steps": ["risk_assessment"],
        # NOTE: crs_score and rejection_prob are persisted to DB in the
        # caller task (ocr_tasks.assess_risk), not stored in graph state
        # to keep the state lean per PRD §0.2 Invariant #5.
        "_crs_score": crs_score,
        "_crs_grade": crs_grade,
        "_rejection_prob": rejection_prob,
        "_risk_features": features,
    }
